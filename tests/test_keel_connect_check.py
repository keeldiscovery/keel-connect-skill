"""Unit tests for scripts/keel_connect_check.py, entirely against the fake runtime fixtures in
tests/fixtures/ (spec 001 tasks.md T006/T008/T010/T011). No real keel-runtime install and no real
Keel Cloud server are used anywhere in this file -- that proof is a separate, cross-repo Java test
in keel-cloud (see README.md).
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "keel_connect_check.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures"
FAKE_RUNTIME_PATH = FIXTURES / "fake_runtime_path"
FAKE_RUNTIME_ON_PATH_DIR = FIXTURES / "fake_runtime_on_path"


class KeelConnectCheckTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name) / "home"
        self._pids_to_kill: list[int] = []

    def tearDown(self):
        for pid in self._pids_to_kill:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self._tmp.cleanup()

    # ------------------------------------------------------------------------------------ helpers

    def run_script(self, scenario: str, extra_args=None, use_runtime_path=True):
        """Runs keel_connect_check.py as a subprocess (matching keel-runtime's own
        test_cli_status.py convention of invoking the CLI as a real subprocess, not importing it),
        returns (parsed_json_or_None, raw_stdout, exit_code).

        By default resolves via --runtime-path against the fake fixture, with PATH scrubbed of
        any real 'keel' so the runtime-path branch is what's actually exercised -- the PATH
        resolution branch itself is tested explicitly and separately, below, with its own fully
        isolated PATH.
        """
        env = os.environ.copy()
        env["FAKE_KEEL_SCENARIO"] = scenario
        env["PATH"] = "/nonexistent-on-purpose"
        env.pop("KEEL_RUNTIME_PATH", None)

        argv = [sys.executable, str(SCRIPT), "--home", str(self.home)]
        if use_runtime_path:
            argv += ["--runtime-path", str(FAKE_RUNTIME_PATH)]

        if extra_args:
            argv += extra_args

        completed = subprocess.run(argv, capture_output=True, text=True, timeout=30, env=env)
        parsed = None
        stdout_lines = [line for line in completed.stdout.splitlines() if line.strip()]
        if len(stdout_lines) == 1:
            try:
                parsed = json.loads(stdout_lines[0])
            except ValueError:
                parsed = None
        return parsed, completed.stdout, completed.returncode

    def track_pid(self, pid: int) -> None:
        self._pids_to_kill.append(pid)

    # =============================================================================== Story 1 (T006)

    def test_not_running_reports_authorization_started_and_launches_detached(self):
        result, raw, code = self.run_script(
            "not_running_then_auth", extra_args=["--wait-seconds", "5"])
        self.assertEqual(code, 0, raw)
        self.assertIsNotNone(result, raw)
        self.assertEqual(result["outcome"], "authorization_started")
        self.assertEqual(result["user_code"], "FAKE-CODE")
        self.assertEqual(result["verification_uri"], "http://fake-cloud.test/verify")
        self.assertIn("pid", result)
        self.assertIn("log_file", result)

        self.track_pid(result["pid"])
        # The launched process must genuinely still be alive -- proves the launch was detached,
        # not blocked on (and torn down with) the script's own already-completed process.
        os.kill(result["pid"], 0)  # raises ProcessLookupError if it isn't

        log_content = Path(result["log_file"]).read_text(encoding="utf-8")
        self.assertIn("KEEL_USER_CODE=FAKE-CODE", log_content)
        self.assertIn("KEEL_VERIFICATION_URI=http://fake-cloud.test/verify", log_content)

    def test_not_running_with_reused_credential_reports_connected(self):
        result, raw, code = self.run_script(
            "not_running_then_instant_connect", extra_args=["--wait-seconds", "5"])
        self.assertEqual(code, 0, raw)
        self.assertEqual(result["outcome"], "connected")
        self.assertEqual(result["agent_session_id"], "instant-agent-session-id")
        self.assertIn("pid", result)
        self.track_pid(result["pid"])

    def test_no_signal_within_wait_reports_timeout_but_leaves_process_running(self):
        started = time.monotonic()
        result, raw, code = self.run_script(
            "not_running_then_no_signal", extra_args=["--wait-seconds", "1"])
        elapsed = time.monotonic() - started

        self.assertEqual(code, 0, raw)
        self.assertEqual(result["outcome"], "authorization_pending_timeout")
        self.assertIn("message", result)
        self.assertIn("pid", result)
        self.track_pid(result["pid"])
        # Bounded wait, not instant and not indefinite.
        self.assertLess(elapsed, 10, "the timeout path must not silently wait far longer than "
                                      "--wait-seconds asked for")

        # The process must still be alive -- a timeout is not a failure, and this script must
        # never kill what it just launched on the user's behalf.
        os.kill(result["pid"], 0)

    def test_launch_passes_through_optional_flags(self):
        result, raw, code = self.run_script(
            "not_running_then_auth",
            extra_args=["--wait-seconds", "5", "--base-url", "http://example.test",
                        "--executor", "stub", "--credential-backend", "file", "--no-browser"])
        self.assertEqual(code, 0, raw)
        self.assertEqual(result["outcome"], "authorization_started")
        self.track_pid(result["pid"])
        # The fake records that connect was invoked; passthrough correctness (the exact argv) is
        # implicitly exercised by the fake's argparse itself raising a usage error (non-zero exit,
        # visible via the script's own internal_error/launch failure paths) if a flag it doesn't
        # recognize were ever sent -- so a clean authorization_started here is itself the
        # assertion that every passthrough flag was accepted.
        marker = self.home / "connect-was-invoked"
        self.assertTrue(marker.exists())

    # =============================================================================== Story 2 (T008)

    def test_already_connected_short_circuits_without_launching(self):
        result, raw, code = self.run_script("already_connected")
        self.assertEqual(code, 0, raw)
        self.assertEqual(result["outcome"], "already_connected")
        self.assertEqual(result["agent_session_id"], "fixed-agent-session-id")
        self.assertEqual(result["base_url"], "http://fake-cloud.test")
        self.assertEqual(result["last_heartbeat_at"], "2026-01-01T00:00:00.000Z")

        # No `connect` launch happened at all -- the fake only ever writes this marker from
        # inside its connect subcommand.
        marker = self.home / "connect-was-invoked"
        self.assertFalse(marker.exists(), "already_connected must not launch a redundant connect")

    # =============================================================================== Story 3 (T010)

    def test_runtime_unavailable_when_runtime_path_has_no_keel_runtime_package(self):
        empty_dir = Path(self._tmp.name) / "not-a-runtime"
        empty_dir.mkdir()
        result, raw, code = self.run_script(
            "not_running_then_auth",
            extra_args=["--runtime-path", str(empty_dir)],
            use_runtime_path=False,  # don't also add the real fixture's --runtime-path
        )
        self.assertEqual(code, 0, raw)
        self.assertEqual(result["outcome"], "runtime_unavailable")
        self.assertIn("message", result)
        self.assertTrue(result["message"])

    def test_runtime_unavailable_when_path_and_env_both_empty(self):
        env = os.environ.copy()
        env["FAKE_KEEL_SCENARIO"] = "not_running_then_auth"
        env["PATH"] = "/nonexistent-on-purpose"
        env.pop("KEEL_RUNTIME_PATH", None)
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--home", str(self.home)],
            capture_output=True, text=True, timeout=30, env=env)
        self.assertEqual(completed.returncode, 0, completed.stdout)
        result = json.loads(completed.stdout.strip())
        self.assertEqual(result["outcome"], "runtime_unavailable")

    def test_path_resolution_wins_over_runtime_path(self):
        """spec FR-002 / research.md §1: a 'keel' on PATH must win even when --runtime-path also
        points at a (different, in this case broken) directory -- proves resolution order, not
        just that the PATH branch works in isolation."""
        env = os.environ.copy()
        env["FAKE_KEEL_SCENARIO"] = "already_connected"
        env["PATH"] = str(FAKE_RUNTIME_ON_PATH_DIR) + os.pathsep + env.get("PATH", "")
        env["KEEL_RUNTIME_PATH"] = "/nonexistent-on-purpose"
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--home", str(self.home)],
            capture_output=True, text=True, timeout=30, env=env)
        self.assertEqual(completed.returncode, 0, completed.stdout)
        result = json.loads(completed.stdout.strip())
        self.assertEqual(result["outcome"], "already_connected")
        self.assertEqual(result["agent_session_id"], "fixed-agent-session-id")

    def test_runtime_path_env_var_used_when_flag_absent(self):
        env = os.environ.copy()
        env["FAKE_KEEL_SCENARIO"] = "already_connected"
        env["PATH"] = "/nonexistent-on-purpose"
        env["KEEL_RUNTIME_PATH"] = str(FAKE_RUNTIME_PATH)
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--home", str(self.home)],
            capture_output=True, text=True, timeout=30, env=env)
        self.assertEqual(completed.returncode, 0, completed.stdout)
        result = json.loads(completed.stdout.strip())
        self.assertEqual(result["outcome"], "already_connected")

    # ============================================================================== internal_error (T011)

    def test_status_crash_reports_internal_error_and_nonzero_exit(self):
        result, raw, code = self.run_script("status_crash")
        self.assertEqual(code, 1, raw)
        self.assertEqual(result["outcome"], "internal_error")
        self.assertIn("message", result)


if __name__ == "__main__":
    unittest.main()
