#!/usr/bin/env python3
"""Fake `keel_runtime` package for `keel_connect_check.py`'s `--runtime-path` resolution branch.

Not a real runtime -- it never talks to any Cloud, never authorizes a device, never runs a job.
Its entire behavior is driven by the `FAKE_KEEL_SCENARIO` environment variable, so the test suite
can make it behave exactly like whichever real `keel-runtime` situation a given test wants to
exercise (spec 001 tasks.md T002). The standalone `keel` executable fixture next to this file's
sibling directory (`fake_runtime_on_path/keel`) implements the identical behavior for the `PATH`
resolution branch -- kept as a second small file rather than shared code, since the two fixtures
are invoked in genuinely different ways (`python3 -m keel_runtime ...` vs. a bare executable) and
duplication here costs nothing.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time


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
    args = build_parser().parse_args(argv)
    scenario = os.environ.get("FAKE_KEEL_SCENARIO", "not_running_then_auth")

    if args.command == "status":
        return _run_status(scenario)
    if args.command == "connect":
        return _run_connect(scenario, args.home)
    return 1  # pragma: no cover -- argparse's required=True makes this dead


def _run_status(scenario: str) -> int:
    if scenario == "already_connected":
        print(json.dumps({
            "running": True,
            "pid": os.getpid(),
            "agent_session_id": "fixed-agent-session-id",
            "base_url": "http://fake-cloud.test",
            "last_heartbeat_at": "2026-01-01T00:00:00.000Z",
            "connected": True,
        }))
        return 0
    if scenario == "status_crash":
        # Deliberately violates spec 021's own contract (non-JSON on stdout, non-zero exit) --
        # this is exactly the "runtime broke its own promise" case keel_connect_check.py's
        # `internal_error` outcome exists for.
        print("not json", flush=True)
        return 1
    print(json.dumps({"running": False}))
    return 0


def _run_connect(scenario: str, home: str | None) -> int:
    if home:
        # A real `connect` would also touch its home directory; harmless for the fake to mirror.
        os.makedirs(home, exist_ok=True)
        marker = os.path.join(home, "connect-was-invoked")
        with open(marker, "w", encoding="utf-8") as handle:
            handle.write(scenario)

    if scenario == "not_running_then_auth":
        print("To authorize this device, visit: http://fake-cloud.test/verify")
        print("Enter code: FAKE-CODE")
        print("KEEL_USER_CODE=FAKE-CODE", flush=True)
        print("KEEL_VERIFICATION_URI=http://fake-cloud.test/verify", flush=True)
    elif scenario == "not_running_then_instant_connect":
        print("KEEL_AGENT_SESSION_ID=instant-agent-session-id", flush=True)
    elif scenario == "not_running_then_no_signal":
        pass  # print nothing -- simulate a hang before any marker line

    # A real `connect` never returns on its own -- it long-polls forever until interrupted.
    # Looping here is what makes the detached-launch behavior (start_new_session=True) genuinely
    # exercised by the tests, rather than trivially true because the fake exits immediately.
    while True:
        time.sleep(0.2)


if __name__ == "__main__":
    sys.exit(main())
