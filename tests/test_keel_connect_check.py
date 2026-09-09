"""Unit tests for scripts/keel_connect_check.py and scripts/_runtime_location.py.

Almost everything here runs against the fake runtime fixtures in tests/fixtures/, which this
repository fully controls -- no Keel Cloud server is contacted anywhere in this file. The one
exception is deliberate and named: `RealBundledRuntimeTestCase` runs the **real** runtime that
`make runtime` copied in, because "the runtime that runs is the one that travelled" (acceptance
A-7) is not something a fake can prove.

The three-tier proof -- this script, a real runtime, a real Keel Cloud -- is a separate cross-repo
test in keel-cloud (`KeelConnectSkillJourneyTest`), not this file.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
SCRIPT = SCRIPTS / "keel_connect_check.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures"
FAKE_CHECKOUT = FIXTURES / "fake_runtime_path"
FAKE_ON_PATH_DIR = FIXTURES / "fake_runtime_on_path"
BUNDLED_RUNTIME = REPO_ROOT / "keel_runtime"

# Everything a session in this repository (or in keel-connect-playground) might have set that
# would otherwise leak into a test's answer. Scrubbed from every subprocess environment, always.
AMBIENT = ("KEEL_HOME", "KEEL_BASE_URL", "KEEL_RUNTIME_PATH", "KEEL_EXECUTOR", "PYTHONPATH",
           "CLAUDECODE", "COPILOT_CLI", "COPILOT_AGENT_SESSION_ID", "AI_AGENT")

# `SIGKILL` does not exist on Windows -- `os.kill(pid, signal.SIGTERM)` there calls
# `TerminateProcess()` unconditionally (there is no catchable-signal distinction to lose), so it is
# just as final a cleanup as SIGKILL is on POSIX. Mirrors keel-runtime's own
# `KILL_SIGNAL = getattr(signal, "SIGKILL", signal.SIGTERM)` (`keel_runtime/disconnect.py`).
TEARDOWN_KILL_SIGNAL = getattr(signal, "SIGKILL", signal.SIGTERM)


def _cleanup_retrying_locked_files(tmp_dir, timeout_seconds=5.0):
    """`tmp_dir.cleanup()`, tolerant of a Windows race this harness runs into on every test that
    tracks a launched `connect`: `TerminateProcess()` (what `os.kill` calls on Windows) *requests*
    termination and returns immediately -- it does not wait for the process to actually exit and
    release what it had open, which here is the launch log inside this very directory, held open
    as that process's own stdout. POSIX allows unlinking a file another process still has open
    outright, so this is a no-op there in practice; on Windows it gives the OS a short, bounded
    window to finish tearing the process down before its temp directory is removed, rather than
    letting that race surface as a `PermissionError` in every test that hits it.
    """
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            tmp_dir.cleanup()
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.2)

sys.path.insert(0, str(SCRIPTS))
import _runtime_location  # noqa: E402
import keel_connect_check  # noqa: E402


def clean_env(**overrides):
    env = os.environ.copy()
    for name in AMBIENT:
        env.pop(name, None)
    env["PATH"] = "/nonexistent-on-purpose"
    env.update({key: str(value) for key, value in overrides.items() if value is not None})
    return env


class SkillHarness(unittest.TestCase):
    """Everything the cases below share: a scratch directory, a way to build a *relocated* skill
    root (the thing a packaging produces), and a way to run the script and get its one JSON line
    back with the contract's hard guarantees already checked."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"
        self.cwd = self.tmp / "cwd"          # deliberately never contains a keel_runtime/
        self.cwd.mkdir()
        self._pids_to_kill = []

    def tearDown(self):
        for pid in self._pids_to_kill:
            try:
                os.kill(pid, TEARDOWN_KILL_SIGNAL)
            except (ProcessLookupError, PermissionError):
                pass
        _cleanup_retrying_locked_files(self._tmp)

    def track_pid(self, pid):
        self._pids_to_kill.append(pid)

    # ------------------------------------------------------------------------------------ helpers

    def fake_on_path_dir(self):
        """A directory to prepend to `PATH` holding a `keel` a founder's shell would run.

        On POSIX this is the fixture itself -- a script starting `#!/usr/bin/env python3`, run
        directly. Windows has no shebang execution and `shutil.which` there matches by `PATHEXT`
        (`.CMD`, `.EXE`, ...), never a bare extensionless name, so the same fixture is unreachable
        by the exact mechanism this branch exists to test. A `.cmd` shim generated per test run --
        rather than a second fixture hand-committed to the repository -- keeps `fake_runtime_on_
        path/keel` the one source both platforms exercise, and ties the shim to `sys.executable`,
        which a static file could not do portably."""
        if os.name != "nt":
            return FAKE_ON_PATH_DIR
        directory = self.tmp / "fake-keel-on-path-windows"
        directory.mkdir(exist_ok=True)
        shim = directory / "keel.cmd"
        content = '@echo off\r\n"%s" "%s" %%*\r\n' % (sys.executable, FAKE_ON_PATH_DIR / "keel")
        with open(shim, "w", newline="", encoding="utf-8") as handle:
            handle.write(content)
        return directory

    def make_skill_root(self, name="skill", bundled=None):
        """A copy of this skill somewhere else, exactly as a packaging would make it: `scripts/`,
        and `keel_runtime/` beside it when `bundled` names a package to put there.

        `_runtime_location` resolves the bundled runtime relative to `scripts/`'s parent (design
        §3.1), so a relocated copy is the honest way to test the bundled branch -- not a flag
        pointing back at this repository.
        """
        root = self.tmp / name
        (root / "scripts").mkdir(parents=True)
        for module in ("keel_connect_check.py", "_runtime_location.py"):
            shutil.copy2(SCRIPTS / module, root / "scripts" / module)
        if bundled is not None:
            shutil.copytree(bundled, root / "keel_runtime",
                            ignore=shutil.ignore_patterns("__pycache__", "*.py[co]"))
        return root

    def run_script(self, script=SCRIPT, args=(), env=None, timeout=60):
        """Runs the script as a real subprocess -- the only way a host ever invokes it -- and
        asserts the guarantees that hold for all seven outcomes before returning: exactly one line
        of JSON on stdout and nothing else (X-1), exit 1 for `internal_error` and 0 for everything
        else, and `environment` present on every shape (guarantee 4).
        """
        completed = subprocess.run(
            [sys.executable, str(script)] + [str(a) for a in args],
            capture_output=True, text=True, timeout=timeout,
            env=clean_env() if env is None else env,
            cwd=str(self.cwd),
        )
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1,
                         "X-1: exactly one line of JSON on stdout, always. Got:\n%r\nstderr:\n%s"
                         % (completed.stdout, completed.stderr))
        result = json.loads(lines[0])
        expected_code = 1 if result["outcome"] == "internal_error" else 0
        self.assertEqual(completed.returncode, expected_code,
                         "exit 0 for every outcome except internal_error. stderr:\n%s"
                         % completed.stderr)
        self.assertIn("environment", result,
                      "guarantee 4: `environment` is present on all seven shapes")
        return result

    def connect_argv(self, home=None):
        """The argv the fake runtime recorded for the `connect` it was asked to run, or None."""
        path = Path(home or self.home) / "connect-argv.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))["argv"]


# =========================================================================== the version gate (X-3)


class VersionGateTestCase(SkillHarness):
    """X-3: the gate is the first executable statement, above every import but `sys`, in syntax
    every Python 3 parses. A founder on 3.8 gets a sentence, not a traceback (acceptance A-5).

    The interpreter running these tests is >= 3.9 by definition, so the old one is faked: a tiny
    runner overwrites `sys.version_info` (and, for the per-OS clauses, `sys.platform`) and then
    executes the real script file, unchanged, through `runpy`.
    """

    def run_under_faked_version(self, version=(3, 8, 2), platform=None, env=None):
        runner = self.tmp / "old_python.py"
        runner.write_text(textwrap.dedent("""\
            import sys, runpy
            sys.version_info = %r
            %s
            sys.argv = ["keel_connect_check.py"]
            runpy.run_path(%r, run_name="__main__")
            """) % (tuple(version) + ("final", 0),
                    ("sys.platform = %r" % platform) if platform else "",
                    str(SCRIPT)), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(runner)], capture_output=True, text=True, timeout=30,
            env=clean_env() if env is None else env, cwd=str(self.cwd))

    def test_old_interpreter_gets_one_json_line_and_exit_zero(self):
        completed = self.run_under_faked_version()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, "", "a sentence, not a traceback")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, completed.stdout)

        result = json.loads(lines[0])
        self.assertEqual(result["outcome"], "python_too_old")
        self.assertEqual(result["found"], "3.8")
        self.assertEqual(result["required"], "3.9")
        self.assertIsNone(result["environment"],
                          "null exactly when no runtime answered (guarantee 4)")

    def test_the_message_names_the_version_and_one_install_command_per_os(self):
        for platform, expected in (
            ("darwin", "xcode-select --install"),
            ("win32", "winget install Python.Python.3.12"),
            ("linux", "apt install python3"),
        ):
            with self.subTest(platform=platform):
                result = json.loads(self.run_under_faked_version(platform=platform).stdout)
                message = result["message"]
                self.assertIn("3.9", message, "the message must name the version needed")
                self.assertIn("3.8", message, "and the version found")
                self.assertIn(expected, message)
                self.assertIn("keel connect", message,
                              "and say what to do once it is installed")

    def test_the_gate_does_not_fire_on_the_floor_itself(self):
        result = json.loads(self.run_under_faked_version(version=(3, 9, 0)).stdout)
        self.assertNotEqual(result["outcome"], "python_too_old",
                            "3.9 is the floor, not below it")

    def test_nothing_is_resolved_or_run_before_the_gate(self):
        """`python_too_old` means *nothing was resolved or run* -- so it must appear even with a
        perfectly good runtime sitting right there, ready to answer."""
        completed = self.run_under_faked_version(
            env=clean_env(KEEL_RUNTIME_PATH=FAKE_CHECKOUT,
                          FAKE_KEEL_SCENARIO="already_connected"))
        self.assertEqual(json.loads(completed.stdout)["outcome"], "python_too_old")


# ========================================================================== resolution order (§3.2)


class ResolutionOrderTestCase(SkillHarness):
    """Design §3.2: a checkout, then the runtime that travelled with the skill, then a `keel` on
    `PATH`. The middle rule is the one that changed -- **the bundled copy now beats a `keel` on
    `PATH`**, so a stranger's install cannot silently shadow the version this skill's own tests
    ran against.
    """

    def path_env(self, **overrides):
        env = clean_env(**overrides)
        tail = "/usr/bin:/bin" if os.name != "nt" \
            else os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
        env["PATH"] = str(self.fake_on_path_dir()) + os.pathsep + tail
        return env

    # ------------------------------------------------------------------- the unit, branch by branch

    def test_resolve_runtime_labels_a_checkout(self):
        located = _runtime_location.resolve_runtime(
            runtime_path=str(FAKE_CHECKOUT), environ={}, which=lambda *a, **k: None)
        self.assertEqual(located.source, _runtime_location.SOURCE_CHECKOUT)
        self.assertEqual(located.argv_prefix, [sys.executable, "-m", "keel_runtime"])
        self.assertEqual(Path(located.pythonpath), FAKE_CHECKOUT)

    def test_resolve_runtime_labels_a_keel_on_path(self):
        # This repository *is* a skill root with a bundled runtime in it, so the third rule is
        # only reachable in a unit test with the second one pointed somewhere empty.
        original = _runtime_location.skill_root
        _runtime_location.skill_root = lambda: str(self.tmp)
        self.addCleanup(setattr, _runtime_location, "skill_root", original)

        located = _runtime_location.resolve_runtime(
            environ={"KEEL_RUNTIME_PATH": "/nonexistent"},
            which=lambda *a, **k: "/usr/local/bin/keel")
        self.assertEqual(located.source, _runtime_location.SOURCE_PATH)
        self.assertEqual(located.argv_prefix, ["/usr/local/bin/keel"])
        self.assertIsNone(located.pythonpath)
        self.assertIsNone(located.child_cwd(), "a bare executable has no directory to be rooted in")

    def test_resolve_runtime_labels_the_bundled_copy(self):
        located = _runtime_location.resolve_runtime(environ={}, which=lambda *a, **k: None)
        self.assertEqual(located.source, _runtime_location.SOURCE_BUNDLED)
        self.assertEqual(Path(located.pythonpath), REPO_ROOT)

    def test_child_env_prepends_the_location_to_pythonpath(self):
        located = _runtime_location.resolve_runtime(
            runtime_path=str(FAKE_CHECKOUT), environ={}, which=lambda *a, **k: None)
        env = located.child_env({"PYTHONPATH": "/somebody/elses/path"})
        self.assertEqual(env["PYTHONPATH"],
                         str(FAKE_CHECKOUT) + os.pathsep + "/somebody/elses/path")
        self.assertEqual(env["PYTHONSAFEPATH"], "1")
        self.assertEqual(Path(located.child_cwd()), FAKE_CHECKOUT,
                         "the shadow guard: `python -m` puts the working directory ahead of "
                         "PYTHONPATH on the 3.9 floor")

    # --------------------------------------------------------------------- the order, end to end

    def test_the_bundled_runtime_beats_a_keel_on_path(self):
        """The reversal this spec exists for. Both are offered; the bundled one must answer.

        The two fixtures name different Keels, so the `environment` in the outcome says which of
        them actually ran -- there is no way to read this assertion the wrong way round.
        """
        root = self.make_skill_root(bundled=FAKE_CHECKOUT / "keel_runtime")
        result = self.run_script(
            script=root / "scripts" / "keel_connect_check.py",
            args=["--home", self.home],
            env=self.path_env(FAKE_KEEL_SCENARIO="already_connected"))
        self.assertEqual(result["outcome"], "already_connected")
        self.assertEqual(result["environment"], "fake-cloud.test",
                         "the bundled runtime answered, not the `keel` on PATH")

    def test_a_checkout_beats_the_bundled_runtime(self):
        """A developer debugging the runtime is never silently testing a release."""
        root = self.make_skill_root(bundled=BUNDLED_RUNTIME)
        result = self.run_script(
            script=root / "scripts" / "keel_connect_check.py",
            args=["--home", self.home, "--runtime-path", FAKE_CHECKOUT],
            env=clean_env(FAKE_KEEL_SCENARIO="already_connected"))
        self.assertEqual(result["outcome"], "already_connected")
        self.assertEqual(result["agent_session_id"], "fixed-agent-session-id")
        self.assertEqual(result["environment"], "fake-cloud.test")

    def test_the_checkout_override_is_read_from_the_environment_too(self):
        root = self.make_skill_root(bundled=BUNDLED_RUNTIME)
        result = self.run_script(
            script=root / "scripts" / "keel_connect_check.py",
            args=["--home", self.home],
            env=clean_env(KEEL_RUNTIME_PATH=FAKE_CHECKOUT,
                          FAKE_KEEL_SCENARIO="already_connected"))
        self.assertEqual(result["outcome"], "already_connected")
        self.assertEqual(result["environment"], "fake-cloud.test")

    def test_a_checkout_that_is_not_one_is_ignored_and_the_next_rule_runs(self):
        """A `--runtime-path` with no `keel_runtime/__main__.py` in it is not a runtime; the order
        carries on rather than failing."""
        empty = self.tmp / "not-a-runtime"
        empty.mkdir()
        root = self.make_skill_root(bundled=FAKE_CHECKOUT / "keel_runtime")
        result = self.run_script(
            script=root / "scripts" / "keel_connect_check.py",
            args=["--home", self.home, "--runtime-path", empty],
            env=clean_env(FAKE_KEEL_SCENARIO="already_connected"))
        self.assertEqual(result["outcome"], "already_connected")
        self.assertEqual(result["environment"], "fake-cloud.test", "the bundled copy answered")

    def test_a_keel_on_path_is_used_when_nothing_travelled_with_the_skill(self):
        """Someone pip-installed it, or packaged it. Still the last rule, but still a rule."""
        root = self.make_skill_root(bundled=None)
        result = self.run_script(
            script=root / "scripts" / "keel_connect_check.py",
            args=["--home", self.home],
            env=self.path_env(FAKE_KEEL_SCENARIO="already_connected"))
        self.assertEqual(result["outcome"], "already_connected")
        self.assertEqual(result["environment"], "stranger-keel.test")

    def test_runtime_unavailable_when_none_of_the_three_resolve(self):
        root = self.make_skill_root(bundled=None)
        result = self.run_script(
            script=root / "scripts" / "keel_connect_check.py",
            args=["--home", self.home])
        self.assertEqual(result["outcome"], "runtime_unavailable")
        self.assertIsNone(result["environment"])
        self.assertTrue(result["message"])

    def test_no_founder_facing_message_names_the_development_override(self):
        """X-4: `--runtime-path` and `KEEL_RUNTIME_PATH` are development overrides. The one
        message a founder can reach without one must not send them looking for them."""
        root = self.make_skill_root(bundled=None)
        message = self.run_script(script=root / "scripts" / "keel_connect_check.py",
                                  args=["--home", self.home])["message"]
        self.assertNotIn("runtime-path", message)
        self.assertNotIn("KEEL_RUNTIME_PATH", message)
        self.assertNotIn("pip install", message,
                         "nothing is installed any more -- there is no such remedy to name")


# ============================================================================== the seven outcomes


class OutcomeTestCase(SkillHarness):
    """Every shape in `specs/001-keel-connect-check/contracts/skill-script-output.md`, from the
    fake runtime. `python_too_old` is the one outcome not reachable from here -- it lives in
    `VersionGateTestCase`, because reaching it means never resolving a runtime at all, and
    `runtime_unavailable` lives in `ResolutionOrderTestCase` for the same reason."""

    def run_against_fake(self, scenario, args=(), **env_extra):
        env = clean_env(FAKE_KEEL_SCENARIO=scenario, **env_extra)
        return self.run_script(
            args=["--home", self.home, "--runtime-path", FAKE_CHECKOUT] + list(args), env=env)

    def test_already_connected(self):
        result = self.run_against_fake("already_connected")
        self.assertEqual(result["outcome"], "already_connected")
        self.assertEqual(result["agent_session_id"], "fixed-agent-session-id")
        self.assertEqual(result["last_heartbeat_at"], "2026-01-01T00:00:00.000Z")
        self.assertEqual(result["environment"], "fake-cloud.test")
        self.assertNotIn("base_url", result,
                         "design §7: this shape loses base_url and gains environment -- one key "
                         "for which Keel, never two")
        self.assertIsNone(self.connect_argv(),
                          "already_connected must not launch a redundant connect")

    def test_authorization_started(self):
        result = self.run_against_fake("not_running_then_auth", args=["--wait-seconds", "5"])
        self.assertEqual(result["outcome"], "authorization_started")
        self.assertEqual(result["user_code"], "FAKE-CODE")
        self.assertEqual(result["verification_uri"], "http://fake-cloud.test/verify")
        self.assertEqual(result["environment"], "fake-cloud.test")
        self.track_pid(result["pid"])
        # Genuinely detached: the launched process outlives the script that started it.
        os.kill(result["pid"], 0)
        self.assertIn("KEEL_USER_CODE=FAKE-CODE",
                      Path(result["log_file"]).read_text(encoding="utf-8"))

    def test_connected(self):
        result = self.run_against_fake("not_running_then_instant_connect",
                                       args=["--wait-seconds", "5"])
        self.assertEqual(result["outcome"], "connected")
        self.assertEqual(result["agent_session_id"], "instant-agent-session-id")
        self.assertEqual(result["environment"], "fake-cloud.test")
        self.track_pid(result["pid"])

    def test_authorization_pending_timeout(self):
        result = self.run_against_fake("not_running_then_no_signal", args=["--wait-seconds", "1"])
        self.assertEqual(result["outcome"], "authorization_pending_timeout")
        self.assertTrue(result["message"])
        self.assertEqual(result["environment"], "fake-cloud.test")
        self.track_pid(result["pid"])
        # A timeout is not a failure: this script never kills what it just launched.
        os.kill(result["pid"], 0)

    def test_internal_error_is_the_only_non_zero_exit(self):
        # The exit code itself is asserted for every outcome, in run_script.
        result = self.run_against_fake("status_crash")
        self.assertEqual(result["outcome"], "internal_error")
        self.assertTrue(result["message"])
        self.assertIsNone(result["environment"],
                          "raised before status returned, so no runtime named a Keel")

    def test_environment_is_null_rather_than_guessed(self):
        """X-5: the skill carries no base URL and no environment table. Against a runtime that
        reports no `environment` at all, it says nothing rather than inventing one."""
        result = self.run_against_fake("status_without_environment")
        self.assertEqual(result["outcome"], "already_connected")
        self.assertIsNone(result["environment"])

    def test_passthrough_flags_reach_connect(self):
        result = self.run_against_fake(
            "not_running_then_auth",
            args=["--wait-seconds", "5", "--base-url", "http://example.test",
                  "--credential-backend", "file", "--no-browser"])
        self.assertEqual(result["outcome"], "authorization_started")
        self.track_pid(result["pid"])
        argv = self.connect_argv()
        self.assertEqual(argv[0], "connect")
        self.assertIn("--base-url", argv)
        self.assertIn("http://example.test", argv)
        self.assertIn("--credential-backend", argv)
        self.assertIn("--no-browser", argv)

    def test_the_home_is_passed_only_when_it_was_given(self):
        """Design §6.3: the runtime derives its own home from the Keel it resolved. The script
        passes `--home` only when it was handed one, and otherwise reports back the home `status`
        named -- which is also where the launch log goes."""
        derived = self.tmp / "derived-home"
        result = self.run_script(
            args=["--runtime-path", FAKE_CHECKOUT, "--wait-seconds", "5"],
            env=clean_env(FAKE_KEEL_SCENARIO="not_running_then_auth", FAKE_KEEL_HOME=derived))
        self.assertEqual(result["outcome"], "authorization_started")
        self.track_pid(result["pid"])
        self.assertEqual(Path(result["log_file"]).parent, derived,
                         "the log goes to the home the runtime named")
        self.assertNotIn("--home", self.connect_argv(home=derived),
                         "nothing was given, so nothing is passed")

    def test_a_given_home_is_passed_through(self):
        result = self.run_against_fake("not_running_then_auth", args=["--wait-seconds", "5"])
        self.track_pid(result["pid"])
        argv = self.connect_argv()
        self.assertIn("--home", argv)
        self.assertIn(str(self.home), argv)

    def test_keel_home_from_the_environment_counts_as_given(self):
        result = self.run_script(
            args=["--runtime-path", FAKE_CHECKOUT, "--wait-seconds", "5"],
            env=clean_env(FAKE_KEEL_SCENARIO="not_running_then_auth", KEEL_HOME=self.home))
        self.assertEqual(result["outcome"], "authorization_started")
        self.track_pid(result["pid"])
        self.assertIn("--home", self.connect_argv())


# ============================================================================= the host (§5.3, D5)


class HostDetectionTestCase(SkillHarness):
    """Design §5.3 step 2. Explicit beats detected; two different answers mean no answer; and no
    outcome shape changes whatever the table says (decision 15)."""

    def test_the_table(self):
        cases = [
            ({"CLAUDECODE": "1"}, "claude"),
            ({"AI_AGENT": "claude-code/1.2.3"}, "claude"),
            ({"COPILOT_CLI": "1"}, "copilot"),
            ({"COPILOT_AGENT_SESSION_ID": "abc-123"}, "copilot"),
            ({"AI_AGENT": "github_copilot_cli"}, "copilot"),
            # Silent.
            ({}, None),
            ({"CLAUDECODE": "0"}, None),
            ({"COPILOT_AGENT_SESSION_ID": "  "}, None),
            ({"AI_AGENT": "some-other-agent"}, None),
            # Two answers mean no answer -- one host's CLI running inside the other's, which is
            # the environment that taught this table those variable names.
            ({"CLAUDECODE": "1", "COPILOT_AGENT_SESSION_ID": "abc-123"}, None),
            ({"AI_AGENT": "claude-code/1.2.3", "COPILOT_CLI": "1"}, None),
            # Two markers agreeing is still one answer.
            ({"COPILOT_CLI": "1", "COPILOT_AGENT_SESSION_ID": "abc-123"}, "copilot"),
        ]
        for environ, expected in cases:
            with self.subTest(environ=environ):
                self.assertEqual(keel_connect_check.detect_host(environ), expected)

    def test_explicit_executor_beats_a_detected_host(self):
        args = keel_connect_check.build_parser().parse_args(["--executor", "scripted"])
        self.assertEqual(keel_connect_check.executor_for(args, {"CLAUDECODE": "1"}), "scripted")

    def test_an_explicit_host_needs_no_detection(self):
        parse = keel_connect_check.build_parser().parse_args
        self.assertEqual(
            keel_connect_check.executor_for(parse(["--host", "copilot"]), {}), "copilot")
        self.assertEqual(
            keel_connect_check.executor_for(parse(["--host", "claude"]), {}), "claude-code",
            "C-12: `claude-code` is a permanent accepted alias, and the name today's runtime knows")

    def test_a_silent_or_contradictory_environment_says_nothing(self):
        parse = keel_connect_check.build_parser().parse_args
        self.assertIsNone(keel_connect_check.executor_for(parse([]), {}))
        self.assertIsNone(keel_connect_check.executor_for(
            parse([]), {"CLAUDECODE": "1", "COPILOT_CLI": "1"}))

    def test_the_detected_host_reaches_connect_as_an_executor(self):
        result = self.run_script(
            args=["--home", self.home, "--runtime-path", FAKE_CHECKOUT, "--wait-seconds", "5"],
            env=clean_env(FAKE_KEEL_SCENARIO="not_running_then_auth", CLAUDECODE="1"))
        self.assertEqual(result["outcome"], "authorization_started")
        self.track_pid(result["pid"])
        argv = self.connect_argv()
        self.assertIn("--executor", argv)
        self.assertEqual(argv[argv.index("--executor") + 1], "claude-code")

    def test_nothing_is_passed_when_the_environment_is_silent(self):
        result = self.run_script(
            args=["--home", self.home, "--runtime-path", FAKE_CHECKOUT, "--wait-seconds", "5"],
            env=clean_env(FAKE_KEEL_SCENARIO="not_running_then_auth"))
        self.track_pid(result["pid"])
        self.assertNotIn("--executor", self.connect_argv(),
                         "the runtime's own executor chain is left untouched")

    def test_the_executor_is_never_sent_to_status(self):
        """`--executor` is passed on `connect` only (§5.3). `already_connected` runs `status` and
        nothing else, and the fake's `status` parser accepts no `--executor` -- so a clean answer
        here is the assertion."""
        result = self.run_script(
            args=["--home", self.home, "--runtime-path", FAKE_CHECKOUT, "--host", "copilot"],
            env=clean_env(FAKE_KEEL_SCENARIO="already_connected"))
        self.assertEqual(result["outcome"], "already_connected")

    def test_no_outcome_shape_gains_a_host_key(self):
        result = self.run_script(
            args=["--home", self.home, "--runtime-path", FAKE_CHECKOUT, "--wait-seconds", "5"],
            env=clean_env(FAKE_KEEL_SCENARIO="not_running_then_auth", CLAUDECODE="1"))
        self.track_pid(result["pid"])
        self.assertEqual(
            set(result), {"outcome", "user_code", "verification_uri", "pid", "log_file",
                          "environment"},
            "decision 15: which executor was chosen is visible in the runtime's log and in "
            "`keel status`, never in a new JSON key")


# ================================================================ the runtime that travelled (A-7)


class RealBundledRuntimeTestCase(SkillHarness):
    """The real `keel_runtime/` that `make runtime` copied in -- not a fake.

    Only `status` and `--version`, and only against an empty home: the runtime's own contract says
    `status` makes no network call and always exits 0 (R-4), so this stays as offline as the rest
    of the file while still proving the one thing no fake can -- that the package sitting beside
    this skill imports and answers under the interpreter that ran the script.
    """

    def setUp(self):
        super().setUp()
        if not (BUNDLED_RUNTIME / "__main__.py").is_file():
            self.skipTest("no bundled runtime here -- run `make runtime` first")

    def test_the_bundled_runtime_answers_from_an_empty_home(self):
        result = self.run_script(args=["--home", self.home, "--wait-seconds", "0"],
                                 env=clean_env(KEEL_BASE_URL="http://localhost:1"))
        # Nothing has ever connected from this home, so `status` says so and a `connect` is
        # launched against a port nothing is listening on -- which is the pending outcome, not an
        # error: a slow or failing start is reported honestly and the process is left alone.
        self.assertEqual(result["outcome"], "authorization_pending_timeout")
        self.assertEqual(result["environment"], "localhost:1",
                         "the environment is the runtime's own answer, relayed unchanged")
        self.track_pid(result["pid"])

    def test_the_bundled_runtime_reports_its_own_version(self):
        located = _runtime_location.resolve_runtime(environ={}, which=lambda *a, **k: None)
        self.assertEqual(located.source, _runtime_location.SOURCE_BUNDLED)
        completed = _runtime_location.run_capturing(located, ["--version"], timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("keel-runtime", completed.stdout)

    def test_runtime_version_names_the_package_that_is_actually_here(self):
        recorded = (REPO_ROOT / "RUNTIME_VERSION").read_text(encoding="utf-8").strip()
        self.assertTrue(recorded, "`make runtime` stamps which runtime this skill carries")
        self.assertIn(recorded.lstrip("v").split("+")[0],
                      (BUNDLED_RUNTIME / "__init__.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
