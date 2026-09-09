#!/usr/bin/env python3
"""Fake `keel_runtime` package, for the resolution branches that run `python3 -m keel_runtime`
(the checkout branch, and -- copied into a temporary skill root -- the bundled branch).

Not a real runtime: it never talks to any Cloud, never authorizes a device, never runs a job. Its
whole behaviour is driven by environment variables so the test suite can make it behave exactly
like whichever real situation a given test wants (spec 003 tasks.md T004):

  FAKE_KEEL_SCENARIO      which of the behaviours below to act out
  FAKE_KEEL_HOME          the home `status` reports when no `--home` was passed -- the real
                          runtime derives its own home from the Keel it resolved (design §6.3),
                          and this fake reports one the same way
  FAKE_KEEL_ENVIRONMENT   the `environment` `status` reports: *which Keel* this is

The standalone `keel` executable fixture (`../fake_runtime_on_path/keel`) implements the identical
behaviour for the `PATH` resolution branch -- kept as a second small file rather than shared code,
since the two are invoked in genuinely different ways (`python3 -m keel_runtime ...` versus a bare
executable found by `shutil.which`) and duplication here costs nothing.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

DEFAULT_ENVIRONMENT = "fake-cloud.test"
CONNECT_ARGV_FILENAME = "connect-argv.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="keel")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status")
    status.add_argument("--home")

    connect = sub.add_parser("connect")
    connect.add_argument("--home")
    connect.add_argument("--base-url")
    connect.add_argument("--executor")
    connect.add_argument("--credential-backend")
    connect.add_argument("--no-browser", action="store_true")

    return parser


def main(argv=None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(raw_argv)
    scenario = os.environ.get("FAKE_KEEL_SCENARIO", "not_running_then_auth")

    if args.command == "status":
        return _run_status(scenario, args.home)
    if args.command == "connect":
        return _run_connect(scenario, args.home, raw_argv)
    return 1  # pragma: no cover -- argparse's required=True makes this dead


def _home_for(explicit):
    return explicit or os.environ.get("FAKE_KEEL_HOME") or None


def _environment_keys(home) -> dict:
    """The keys spec `004-shipped-runtime` FR-009 puts in **both** status shapes."""
    environment = os.environ.get("FAKE_KEEL_ENVIRONMENT", DEFAULT_ENVIRONMENT)
    return {
        "home": home,
        "base_url": "http://" + environment,
        "environment": environment,
        "executor": "claude-code",
        "executor_on_path": False,
    }


def _run_status(scenario: str, home_flag) -> int:
    home = _home_for(home_flag)

    if scenario == "status_crash":
        # Deliberately violates the runtime's own contract (non-JSON on stdout, non-zero exit) --
        # exactly the "runtime broke its own promise" case `internal_error` exists for.
        print("not json", flush=True)
        return 1

    if scenario == "status_without_environment":
        # A runtime older than spec `004-shipped-runtime`: no `home`, no `environment`. The skill
        # must report `environment: null` rather than guess one (invariant X-5).
        print(json.dumps({
            "running": True,
            "pid": os.getpid(),
            "agent_session_id": "fixed-agent-session-id",
            "base_url": "http://fake-cloud.test",
            "last_heartbeat_at": "2026-01-01T00:00:00.000Z",
            "connected": True,
        }))
        return 0

    if scenario == "already_connected":
        result = {
            "running": True,
            "pid": os.getpid(),
            "agent_session_id": "fixed-agent-session-id",
            "last_heartbeat_at": "2026-01-01T00:00:00.000Z",
            "connected": True,
        }
    else:
        result = {"running": False}

    result.update(_environment_keys(home))
    print(json.dumps(result))
    return 0


def _run_connect(scenario: str, home_flag, raw_argv) -> int:
    home = _home_for(home_flag)
    if home:
        # A real `connect` would also touch its home directory; harmless for the fake to mirror.
        # The whole argv is recorded so a test can assert exactly which flags were passed through
        # -- `--executor` above all (design §5.3).
        os.makedirs(home, exist_ok=True)
        with open(os.path.join(home, CONNECT_ARGV_FILENAME), "w", encoding="utf-8") as handle:
            json.dump({"scenario": scenario, "argv": raw_argv}, handle)

    if scenario == "not_running_then_auth":
        print("KEEL_ENVIRONMENT=fake-cloud.test base_url=http://fake-cloud.test", flush=True)
        print("To authorize this device, visit: http://fake-cloud.test/verify")
        print("Enter code: FAKE-CODE")
        print("KEEL_USER_CODE=FAKE-CODE", flush=True)
        print("KEEL_VERIFICATION_URI=http://fake-cloud.test/verify", flush=True)
    elif scenario == "not_running_then_instant_connect":
        print("KEEL_AGENT_SESSION_ID=instant-agent-session-id", flush=True)
    elif scenario == "not_running_then_no_signal":
        pass  # print nothing -- simulate a hang before any marker line

    # A real `connect` never returns on its own -- it long-polls forever until interrupted.
    # Looping here is what makes the detached-launch behaviour genuinely exercised by the tests,
    # rather than trivially true because the fake exited immediately.
    while True:
        time.sleep(0.2)


if __name__ == "__main__":
    sys.exit(main())
