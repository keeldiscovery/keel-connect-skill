"""Unit tests for scripts/keel_disconnect.py -- the door out.

Every outcome in `specs/002-keel-disconnect/contracts/skill-disconnect-output.md`, run through
**both** resolution branches (the runtime that travelled inside the skill, and a `keel` on `PATH`),
against the fake runtime fixtures in tests/fixtures/ -- which this repository fully controls. No
Keel Cloud server is contacted anywhere in this file except by the one class that says so in its
name and skips itself when nothing is listening.

`RealDisconnectTestCase` is that exception, and it is the point of the spec: the **real** bundled
runtime, a real `keel connect` against a real keel-cloud, then this script twice -- `disconnected`,
then `not_running`. A fake can prove the translation; only a real process can prove the door.
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
SCRIPT = SCRIPTS / "keel_disconnect.py"
CONNECT_SCRIPT = SCRIPTS / "keel_connect_check.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures"
FAKE_CHECKOUT = FIXTURES / "fake_runtime_path"
FAKE_ON_PATH_DIR = FIXTURES / "fake_runtime_on_path"
FAKE_NO_DISCONNECT = FIXTURES / "fake_runtime_no_disconnect"
BUNDLED_RUNTIME = REPO_ROOT / "keel_runtime"

AMBIENT = ("KEEL_HOME", "KEEL_BASE_URL", "KEEL_RUNTIME_PATH", "KEEL_EXECUTOR", "PYTHONPATH",
           "CLAUDECODE", "COPILOT_CLI", "COPILOT_AGENT_SESSION_ID", "AI_AGENT")

sys.path.insert(0, str(SCRIPTS))
import keel_disconnect  # noqa: E402


def clean_env(**overrides):
    env = os.environ.copy()
    for name in AMBIENT:
        env.pop(name, None)
    env["PATH"] = "/nonexistent-on-purpose"
    env.update({key: str(value) for key, value in overrides.items() if value is not None})
    return env


# The key set the contract documents for each shape. Asserted **exactly**, in both directions:
# guarantee 1 says every key in a shape is in every occurrence of it, and guarantee 2 says no key
# outside a shape appears at all.
SHAPE_KEYS = {
    "disconnected": {"outcome", "pid", "waited_ms", "signal", "environment"},
    "not_running": {"outcome", "environment"},
    "stale_pid_cleared": {"outcome", "pid", "environment"},
    "did_not_stop": {"outcome", "pid", "waited_ms", "message", "environment"},
    "runtime_unavailable": {"outcome", "message", "environment"},
    "internal_error": {"outcome", "message", "environment"},
}


class DisconnectHarness(unittest.TestCase):
    """A scratch directory, a relocated skill root (the thing a packaging produces), and one way to
    run the script that checks the contract's hard guarantees before returning anything."""

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
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        self._tmp.cleanup()

    def track_pid(self, pid):
        self._pids_to_kill.append(pid)

    # ------------------------------------------------------------------------------------ helpers

    def make_skill_root(self, name="skill", bundled=None):
        """A copy of this skill somewhere else, as a packaging would make it. `_runtime_location`
        resolves the bundled runtime relative to `scripts/`'s parent, so a relocated copy is the
        honest way to exercise that branch."""
        root = self.tmp / name
        (root / "scripts").mkdir(parents=True)
        for module in ("keel_disconnect.py", "keel_connect_check.py", "_runtime_location.py"):
            shutil.copy2(SCRIPTS / module, root / "scripts" / module)
        if bundled is not None:
            shutil.copytree(bundled, root / "keel_runtime",
                            ignore=shutil.ignore_patterns("__pycache__", "*.py[co]"))
        return root

    def run_script(self, script=SCRIPT, args=(), env=None, timeout=60):
        """The script as a real subprocess -- the only way a host ever invokes it -- with the
        guarantees that hold for all six outcomes asserted before returning: exactly one line of
        JSON on stdout and nothing else, exit 1 for `internal_error` and 0 for everything else
        (guarantee 5), `environment` present on every shape (guarantee 6), and the documented key
        set exactly (guarantees 1 and 2)."""
        completed = subprocess.run(
            [sys.executable, str(script)] + [str(a) for a in args],
            capture_output=True, text=True, timeout=timeout,
            env=clean_env() if env is None else env,
            cwd=str(self.cwd),
        )
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1,
                         "guarantee 1: exactly one line of JSON on stdout, always. Got:\n%r\n"
                         "stderr:\n%s" % (completed.stdout, completed.stderr))
        result = json.loads(lines[0])
        expected_code = 1 if result["outcome"] == "internal_error" else 0
        self.assertEqual(completed.returncode, expected_code,
                         "guarantee 5: exit 0 for every outcome except internal_error. stderr:\n%s"
                         % completed.stderr)
        self.assertIn("environment", result,
                      "guarantee 6: `environment` is present on all six shapes")
        self.assertIn(result["outcome"], SHAPE_KEYS,
                      "guarantee 5: `outcome` is always one of the six documented values")
        self.assertEqual(set(result), SHAPE_KEYS[result["outcome"]],
                         "guarantees 1 and 2: the documented key set for `%s`, exactly"
                         % result["outcome"])
        return result

    def disconnect_argv(self, home=None):
        """The argv the fake runtime recorded for the `disconnect` it was asked to run, or None."""
        path = Path(home or self.home) / "disconnect-argv.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))["argv"]

    def connect_argv(self, home=None):
        """S3's marker: the fake writes this only when it was asked to run a `connect`."""
        path = Path(home or self.home) / "connect-argv.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))["argv"]


# ================================================================= every outcome, through both branches


class OutcomeTestCase(DisconnectHarness):
    """The six shapes of `specs/002-keel-disconnect/contracts/skill-disconnect-output.md`, each run
    through **both** the way a founder gets the runtime (bundled beside the script) and the way
    someone who installed their own gets it (a `keel` on `PATH`).

    The two fixtures name different Keels on purpose, so the `environment` in the answer says which
    of the two actually ran and no assertion here can be read the wrong way round.
    """

    BRANCHES = ("bundled", "path")

    def run_branch(self, branch, scenario, args=(), **env_extra):
        """One run of the script, resolved the way `branch` says, against `scenario`."""
        if branch == "bundled":
            root = self.make_skill_root(bundled=FAKE_CHECKOUT / "keel_runtime")
            env = clean_env(FAKE_KEEL_SCENARIO=scenario, **env_extra)
            script = root / "scripts" / "keel_disconnect.py"
        else:
            # A relocated skill with **no** runtime beside it, and the fake `keel` on PATH: the
            # third resolution rule, reached honestly rather than by a flag.
            root = self.make_skill_root(name="skill-no-runtime")
            env = clean_env(FAKE_KEEL_SCENARIO=scenario, **env_extra)
            env["PATH"] = str(FAKE_ON_PATH_DIR) + os.pathsep + "/usr/bin:/bin"
            script = root / "scripts" / "keel_disconnect.py"
        return self.run_script(script=script, args=["--home", self.home] + list(args), env=env)

    def environment_for(self, branch):
        """Which Keel each fixture names -- the fingerprint that says which one answered."""
        return "fake-cloud.test" if branch == "bundled" else "stranger-keel.test"

    # ---------------------------------------------------------------------------- the four mapped

    def test_disconnected(self):
        """`stopped` becomes `disconnected`: the runtime was running, was signalled, and has been
        **observed** gone (guarantee 7)."""
        for branch in self.BRANCHES:
            with self.subTest(branch=branch):
                result = self.run_branch(branch, "stopped")
                self.assertEqual(result["outcome"], "disconnected")
                self.assertEqual(result["pid"], 41213)
                self.assertEqual(result["waited_ms"], 84)
                self.assertEqual(result["signal"], "SIGTERM")
                self.assertEqual(result["environment"], self.environment_for(branch))

    def test_disconnected_after_escalation_reports_sigkill(self):
        for branch in self.BRANCHES:
            with self.subTest(branch=branch):
                result = self.run_branch(branch, "stopped_sigkill")
                self.assertEqual(result["outcome"], "disconnected")
                self.assertEqual(result["signal"], "SIGKILL")
                self.assertGreaterEqual(result["waited_ms"], 10000,
                                        "an escalation waited out the grace first")

    def test_not_running(self):
        """Nothing was running on this home; nothing was done. Not an error at either level."""
        for branch in self.BRANCHES:
            with self.subTest(branch=branch):
                result = self.run_branch(branch, "not_running")
                self.assertEqual(result["outcome"], "not_running")
                self.assertEqual(result["environment"], self.environment_for(branch))

    def test_stale_pid_cleared(self):
        for branch in self.BRANCHES:
            with self.subTest(branch=branch):
                result = self.run_branch(branch, "stale_pid")
                self.assertEqual(result["outcome"], "stale_pid_cleared")
                self.assertEqual(result["pid"], 40118)

    def test_did_not_stop(self):
        """`timeout` becomes `did_not_stop`, and carries the sentence the skill relays: the process
        is stuck in a call the operating system will not interrupt."""
        for branch in self.BRANCHES:
            with self.subTest(branch=branch):
                result = self.run_branch(branch, "timeout")
                self.assertEqual(result["outcome"], "did_not_stop")
                self.assertEqual(result["pid"], 41213)
                self.assertEqual(result["waited_ms"], 15003)
                self.assertIn("SIGKILL", result["message"])

    # ------------------------------------------------------------------- the two that are ours

    def test_runtime_unavailable(self):
        """No checkout, no runtime beside the skill, no `keel` on `PATH`. The message names neither
        the development override (X-4) nor an install, because nothing is installed."""
        root = self.make_skill_root(name="empty-skill")
        result = self.run_script(script=root / "scripts" / "keel_disconnect.py",
                                 args=["--home", self.home])
        self.assertEqual(result["outcome"], "runtime_unavailable")
        self.assertIsNone(result["environment"])
        lowered = result["message"].lower()
        for forbidden in ("keel_runtime_path", "--runtime-path", "pip install"):
            self.assertNotIn(forbidden, lowered,
                             "X-4: no founder-facing message names a development override, and "
                             "nothing is installed any more")

    def test_internal_error_when_the_runtime_crashes(self):
        for branch in self.BRANCHES:
            with self.subTest(branch=branch):
                result = self.run_branch(branch, "disconnect_crash")
                self.assertEqual(result["outcome"], "internal_error")
                self.assertIsNone(result["environment"],
                                  "nothing that honours the contract came back, so no runtime "
                                  "named a Keel (X-5)")

    def test_internal_error_when_the_runtime_prints_two_lines(self):
        result = self.run_branch("bundled", "disconnect_two_lines")
        self.assertEqual(result["outcome"], "internal_error")
        self.assertIn("one line", result["message"])

    def test_internal_error_when_the_runtime_reports_an_outcome_we_do_not_know(self):
        result = self.run_branch("bundled", "unknown_outcome")
        self.assertEqual(result["outcome"], "internal_error")
        self.assertIn("newer than this skill", result["message"])

    def test_internal_error_names_the_missing_subcommand_on_an_old_runtime(self):
        """The likeliest cause in practice, exercised against a fixture that genuinely has no
        `disconnect` subparser -- so this is a real argparse failure (exit 2, usage on stderr) and
        not a mock of one. "Update your keel-runtime" is a remedy; "something went wrong" is not.
        """
        root = self.make_skill_root(name="old-skill",
                                    bundled=FAKE_NO_DISCONNECT / "keel_runtime")
        result = self.run_script(script=root / "scripts" / "keel_disconnect.py",
                                 args=["--home", self.home])
        self.assertEqual(result["outcome"], "internal_error")
        self.assertIn("predates the disconnect command", result["message"])
        self.assertIn("needs updating", result["message"])


# ============================================================== it cannot start anything (S3)


class NeverStartsAnythingTestCase(DisconnectHarness):
    """Invariant S3 and guarantee 3: this script never starts a `keel connect`, under any outcome.

    Asserted the only way worth asserting it -- by the **absence of the fixtures' own
    `connect-was-invoked` marker** after every outcome, rather than by reading the source.
    """

    def test_no_outcome_launches_a_connect(self):
        for scenario in ("stopped", "not_running", "stale_pid", "timeout", "disconnect_crash"):
            with self.subTest(scenario=scenario):
                home = self.tmp / ("home-" + scenario)
                self.run_script(args=["--home", home, "--runtime-path", FAKE_CHECKOUT],
                                env=clean_env(FAKE_KEEL_SCENARIO=scenario))
                self.assertIsNone(self.connect_argv(home=home),
                                  "S3: the fixture records every connect it is asked to run, and "
                                  "there must never be one")

    def test_the_script_has_no_launch_path_at_all(self):
        """The other half of "not capable of it": nothing in this file can start a detached
        process. A `Popen` here would be a bug the marker test above could miss on a run where the
        fake happened not to be reached."""
        source = SCRIPT.read_text(encoding="utf-8")
        for forbidden in ("Popen", "start_new_session", "CREATE_NEW_PROCESS_GROUP", '"connect"'):
            self.assertNotIn(forbidden, source,
                             "guarantee 3: there is no launch path in this script")


# ======================================================================= the home, resolved once


class HomeTestCase(DisconnectHarness):
    """The two scripts must resolve one home from one set of inputs, or the door out does not open
    on the door in. `resolve_given_home` is the same rule in both files (design §6.3)."""

    def run_against_fake(self, args=(), **env_extra):
        env = clean_env(FAKE_KEEL_SCENARIO="not_running", **env_extra)
        return self.run_script(args=["--runtime-path", FAKE_CHECKOUT] + list(args), env=env)

    def test_a_given_home_is_passed_through(self):
        self.run_against_fake(args=["--home", self.home])
        argv = self.disconnect_argv()
        self.assertEqual(argv[0], "disconnect")
        self.assertIn("--home", argv)
        self.assertIn(str(self.home), argv)

    def test_keel_home_from_the_environment_counts_as_given(self):
        self.run_against_fake(KEEL_HOME=self.home)
        self.assertIn("--home", self.disconnect_argv())

    def test_the_flag_beats_the_environment(self):
        other = self.tmp / "other-home"
        self.run_against_fake(args=["--home", self.home], KEEL_HOME=other)
        self.assertIn(str(self.home), self.disconnect_argv())
        self.assertFalse((other / "disconnect-argv.json").exists(),
                         "the flag wins outright; the environment's home is never acted on")

    def test_nothing_given_means_nothing_passed(self):
        """The runtime derives its own home from the Keel it resolves. A guessed `~/.keel` would
        name a different directory from the one the sibling script connected on, so this script
        does not guess one."""
        derived = self.tmp / "derived-home"
        self.run_against_fake(FAKE_KEEL_HOME=derived)
        self.assertNotIn("--home", self.disconnect_argv(home=derived),
                         "nothing was given, so nothing is passed")

    def test_resolve_given_home_is_the_connect_script_s_rule(self):
        """The unit, both directions, so the two files cannot drift apart quietly."""
        sys.path.insert(0, str(SCRIPTS))
        import keel_connect_check  # noqa: E402 -- imported here, beside the assertion it is for

        args = keel_disconnect.build_parser().parse_args(["--home", "~/somewhere"])
        self.assertEqual(keel_disconnect.resolve_given_home(args, environ={}),
                         os.path.expanduser("~/somewhere"))
        self.assertIsNone(keel_disconnect.resolve_given_home(
            keel_disconnect.build_parser().parse_args([]), environ={}))
        self.assertEqual(
            keel_disconnect.resolve_given_home(
                keel_disconnect.build_parser().parse_args([]), environ={"KEEL_HOME": "/a/home"}),
            keel_connect_check.resolve_given_home(
                keel_connect_check.build_parser().parse_args([]), environ={"KEEL_HOME": "/a/home"}))


# ==================================================================== the translation, as a unit


class TranslationTestCase(unittest.TestCase):
    """`translate` alone: the runtime's four names into four of the six, and **only** the keys the
    contract names. `home` and `base_url`, which the runtime puts on all four of its own shapes,
    are dropped -- `environment` is the one key for which Keel, never two (design §7)."""

    def translate(self, **runtime_shape):
        shape = {"home": "/somewhere/.keel/cloud", "base_url": "https://cloud.keel.example",
                 "environment": "cloud"}
        shape.update(runtime_shape)
        return keel_disconnect.translate(shape)

    def test_the_four_names(self):
        self.assertEqual(self.translate(outcome="stopped", pid=1, waited_ms=2,
                                        signal="SIGTERM")["outcome"], "disconnected")
        self.assertEqual(self.translate(outcome="not_running")["outcome"], "not_running")
        self.assertEqual(self.translate(outcome="stale_pid_cleared", pid=1)["outcome"],
                         "stale_pid_cleared")
        self.assertEqual(self.translate(outcome="timeout", pid=1, waited_ms=2)["outcome"],
                         "did_not_stop")

    def test_the_address_keys_do_not_come_up(self):
        for shape in ({"outcome": "not_running"},
                      {"outcome": "stopped", "pid": 1, "waited_ms": 2, "signal": "SIGTERM"},
                      {"outcome": "stale_pid_cleared", "pid": 1},
                      {"outcome": "timeout", "pid": 1, "waited_ms": 2}):
            with self.subTest(outcome=shape["outcome"]):
                translated = self.translate(**shape)
                self.assertNotIn("home", translated)
                self.assertNotIn("base_url", translated)
                self.assertEqual(translated["environment"], "cloud")

    def test_the_key_set_of_every_shape(self):
        self.assertEqual(set(self.translate(outcome="stopped", pid=1, waited_ms=2,
                                            signal="SIGTERM")), SHAPE_KEYS["disconnected"])
        self.assertEqual(set(self.translate(outcome="not_running")), SHAPE_KEYS["not_running"])
        self.assertEqual(set(self.translate(outcome="stale_pid_cleared", pid=1)),
                         SHAPE_KEYS["stale_pid_cleared"])
        self.assertEqual(set(self.translate(outcome="timeout", pid=1, waited_ms=2)),
                         SHAPE_KEYS["did_not_stop"])

    def test_an_environment_the_runtime_did_not_name_is_null_rather_than_guessed(self):
        translated = keel_disconnect.translate({"outcome": "not_running"})
        self.assertIsNone(translated["environment"], "X-5: say nothing rather than guess")


# ============================================================== the real thing (the whole point)


class RealDisconnectTestCase(DisconnectHarness):
    """The **real** bundled runtime, connected to a **real** keel-cloud, stopped by this script.

    Everything above proves the translation. This proves the door: a `keel connect` launched by
    the sibling script authorizes a device, connects, and writes a heartbeat; this script stops
    that process and observes it gone (`disconnected`); a second run finds nothing to stop
    (`not_running` -- idempotence, D10).

    It needs a keel-cloud listening at `KEEL_BASE_URL` (the playground's is
    `http://localhost:18081`, brought up by `make up PROFILE=playground` in keel-e2e-eval) and
    **skips itself** when nothing is there, so the offline suite stays offline and CI is unaffected.
    `KEEL_HOME` is a scratch directory in every case: this test never touches a home a founder has
    connected, and never reads or writes a real credential.

    **One deliberate exception to this repository's scope discipline**, and the only place it
    appears: `approve_device` below speaks keel-cloud's own wire to say APPROVE. It stands in for
    the founder's browser click at `/connect` -- the one step of this walk that is a human, and the
    one thing a test cannot shell out to the runtime for. Everything else here goes through the two
    scripts' documented contracts, exactly as a host does. The full referee's version of this walk,
    with the browser, is keel-e2e-eval's S-001 tail (spec `011-keel-disconnect`); this is the
    smallest thing that proves the door in the repository the door lives in.
    """

    BASE_URL = (os.environ.get("KEEL_BASE_URL") or "http://localhost:18081").rstrip("/")

    # A founder of this test's own, never the eval profile's: two suites that share an account
    # share a password, and the first one to change it breaks the other.
    FOUNDER_NAME = "Skill Suite Founder"
    FOUNDER_EMAIL = "skill-suite@keel-connect-skill.test"
    FOUNDER_PASSWORD = "skill-suite-password-1"

    def setUp(self):
        super().setUp()
        if not (BUNDLED_RUNTIME / "__main__.py").is_file():
            self.skipTest("no bundled runtime here -- run `make runtime` first")
        if not self._listening(self.BASE_URL):
            self.skipTest("no keel-cloud listening at %s -- start the playground stack to run "
                          "this one" % self.BASE_URL)

    @staticmethod
    def _listening(base_url):
        without_scheme = base_url.split("://", 1)[-1].split("/", 1)[0]
        host, _, port = without_scheme.partition(":")
        try:
            connection = socket.create_connection((host or "localhost", int(port or 80)),
                                                  timeout=2)
        except OSError:
            return False
        connection.close()
        return True

    # -------------------------------------------------------------------------------- the walk

    def test_connect_then_disconnect_then_disconnect_again(self):
        # 1. Start a real runtime the way a founder does -- through the sibling script, never by
        #    shelling `python3 -m keel_runtime` directly.
        started = self.run_connect()
        self.assertIn(started["outcome"], ("authorization_started", "connected"),
                      "a real runtime started against %s: %s" % (self.BASE_URL, started))
        self.track_pid(started["pid"])
        self.assertEqual(started["environment"], self.expected_environment(),
                         "the environment is the runtime's own answer, relayed unchanged")

        # 2. The founder's browser click, and nothing more than it.
        if started["outcome"] == "authorization_started":
            self.approve_device(started["user_code"])

        # A connected heartbeat appears a moment after the agent session exists. Waiting for it
        # is waiting for "there is now a connected runtime on this home, credential stored".
        self.assertTrue(self.await_heartbeat(),
                        "the runtime never wrote a heartbeat on %s; its log said:\n%s"
                        % (self.home, self.launch_log()))

        # 3. The door out.
        stopped = self.run_script(args=["--home", self.home], env=self.real_env())
        self.assertEqual(stopped["outcome"], "disconnected",
                         "the real runtime was stopped and observed gone")
        self.assertEqual(stopped["environment"], self.expected_environment())
        self.assertEqual(stopped["signal"], "SIGTERM",
                         "a runtime that honours its own shutdown handler never needs escalating")
        self.assertFalse(self.pid_alive(stopped["pid"]),
                         "guarantee 7: `disconnected` is emitted only after the pid was observed "
                         "not alive")
        self.assertFalse(self.heartbeat().exists(),
                         "a `disconnected` leaves no heartbeat behind")

        # 4. Idempotent: a second run against the same home is `not_running` (D10).
        again = self.run_script(args=["--home", self.home], env=self.real_env())
        self.assertEqual(again["outcome"], "not_running")

        # 5. And the credential is untouched by either run: disconnect stops a process, it does
        #    not forget a machine (D7). A later "keel connect" here needs no device code.
        self.assertTrue((self.home / "credentials.json").exists(),
                        "D7: no outcome of a disconnect touches the credential")

    # ------------------------------------------------------------------------------------ helpers

    def real_env(self):
        return clean_env(KEEL_HOME=self.home, KEEL_BASE_URL=self.BASE_URL,
                         PATH=os.environ.get("PATH", "/usr/bin:/bin"))

    def heartbeat(self):
        return self.home / "runtime.heartbeat.json"

    def launch_log(self):
        path = self.home / "keel-connect-check.launch.log"
        return path.read_text(encoding="utf-8") if path.exists() else "(no log)"

    def run_connect(self):
        """The sibling script, unmodified, with a scratch home and no browser."""
        completed = subprocess.run(
            [sys.executable, str(CONNECT_SCRIPT), "--home", str(self.home),
             "--wait-seconds", "30", "--no-browser", "--credential-backend", "file"],
            capture_output=True, text=True, timeout=180, env=self.real_env(), cwd=str(self.cwd))
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, "stdout:\n%s\nstderr:\n%s"
                         % (completed.stdout, completed.stderr))
        return json.loads(lines[0])

    def approve_device(self, user_code):
        """Stand in for the founder at keel-cloud's `/connect` screen: sign in, then APPROVE.

        The two calls keel-web makes for that click and no others -- a founder session cookie, and
        `POST /v2/device-authorizations/decision`. Skips rather than fails when this keel-cloud
        already belongs to somebody else's founder, because that is a fact about the machine the
        test is running on, not a fact about the skill.
        """
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

        def call(path, payload=None, camel=True):
            url = self.BASE_URL + path
            data = None if payload is None else json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(
                url, data=data, method="GET" if data is None else "POST",
                headers={"Content-Type": "application/json"})
            with opener.open(request, timeout=15) as response:
                body = response.read().decode("utf-8")
            return json.loads(body) if body.strip() else {}

        try:
            if not call("/v2/setup")["accountExists"]:
                call("/v2/setup", {"name": self.FOUNDER_NAME, "email": self.FOUNDER_EMAIL,
                                   "password": self.FOUNDER_PASSWORD})
            else:
                call("/v2/login", {"email": self.FOUNDER_EMAIL,
                                   "password": self.FOUNDER_PASSWORD})
        except urllib.error.HTTPError as exc:
            self.skipTest("this keel-cloud at %s has a founder account this test does not know "
                          "the password for (%s) -- `make down PROFILE=playground` and up again "
                          "to run it" % (self.BASE_URL, exc))

        decision = call("/v2/device-authorizations/decision",
                        {"user_code": user_code, "decision": "APPROVE"})
        self.assertEqual(decision.get("status"), "APPROVED", decision)

    def await_heartbeat(self, seconds=60.0):
        """Waits for a *connected* heartbeat. Since keel-runtime 80b883b the file exists from the
        moment `connect` starts (state `awaiting_approval`, no agent session), so its mere presence
        no longer means the credential has been stored; the walk needs the session to exist."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self.heartbeat().exists():
                try:
                    record = json.loads(self.heartbeat().read_text())
                except (OSError, ValueError):
                    record = {}
                if record.get("state", "connected") != "awaiting_approval" \
                        and record.get("agent_session_id"):
                    return True
            time.sleep(0.25)
        return False

    def expected_environment(self):
        """What the runtime calls this Keel: `host:port` for anything but the built-in default."""
        return self.BASE_URL.split("://", 1)[-1]

    @staticmethod
    def pid_alive(pid):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True


if __name__ == "__main__":
    unittest.main()
