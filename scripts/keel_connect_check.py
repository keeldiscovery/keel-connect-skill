#!/usr/bin/env python3
"""Checks whether a local `keel-runtime` (keel-cloud spec 020) is connected to Keel Cloud, and
launches `keel connect` in the background if not.

This is the entire implementation behind the `keel-connect` Claude Code skill (`../SKILL.md`).
It never talks to Keel Cloud itself -- it only shells out to `keel-runtime status` (keel-cloud
spec 021, a fast, offline, local check) and, when nothing is running, launches a detached
`keel connect` and watches its log for the human-facing signal lines it already prints.

Standard library only (spec 001 FR-009) -- no dependency beyond what a bare `python3` provides,
since Claude Code invokes this as a plain subprocess.

Stable output contract: `../specs/001-keel-connect-check/contracts/skill-script-output.md`. Every
outcome shape documented there is produced from exactly one place in this file (`_emit`), so the
contract and the implementation cannot drift apart silently.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_WAIT_SECONDS = 8.0
STATUS_SUBPROCESS_TIMEOUT_SECONDS = 15.0
LAUNCH_SIGNAL_POLL_INTERVAL_SECONDS = 0.25
LAUNCH_LOG_FILENAME = "keel-connect-check.launch.log"

USER_CODE_PREFIX = "KEEL_USER_CODE="
VERIFICATION_URI_PREFIX = "KEEL_VERIFICATION_URI="
AGENT_SESSION_ID_PREFIX = "KEEL_AGENT_SESSION_ID="


@dataclass
class RuntimeLocation:
    """Where to invoke `status`/`connect` from -- either a `keel` executable found on `PATH`
    (argv prefix `[<path-to-keel>]`, no fixed cwd needed) or a dev-mode checkout invoked as
    `python3 -m keel_runtime` with that checkout as the subprocess's cwd (research.md §1).
    """

    argv_prefix: list[str]
    cwd: Optional[Path]


# --------------------------------------------------------------------------------- argument parsing


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="keel_connect_check",
        description=(
            "Check whether a keel-runtime is connected to Keel Cloud; launch `keel connect` "
            "in the background if not. See specs/001-keel-connect-check/contracts/"
            "skill-script-output.md for this script's stable JSON output contract."
        ),
    )
    parser.add_argument(
        "--runtime-path",
        dest="runtime_path",
        default=None,
        help="dev-mode keel-runtime checkout directory, used only when no 'keel' command is on "
        "PATH (falls back to the KEEL_RUNTIME_PATH environment variable)",
    )
    parser.add_argument("--base-url", dest="base_url", default=None,
                         help="passed through to 'keel connect' if a launch is needed")
    parser.add_argument("--executor", dest="executor", default=None,
                         help="passed through to 'keel connect' if a launch is needed")
    parser.add_argument(
        "--credential-backend",
        dest="credential_backend",
        choices=["auto", "file", "keyring"],
        default=None,
        help="passed through to 'keel connect' if a launch is needed",
    )
    parser.add_argument(
        "--no-browser",
        dest="no_browser",
        action="store_true",
        help="passed through to 'keel connect' if a launch is needed",
    )
    parser.add_argument(
        "--home",
        dest="home",
        default=None,
        help="overrides KEEL_HOME for both the status check and any launch (falls back to the "
        "KEEL_HOME environment variable, then ~/.keel)",
    )
    parser.add_argument(
        "--wait-seconds",
        dest="wait_seconds",
        type=float,
        default=DEFAULT_WAIT_SECONDS,
        help=f"how long to watch a launched connect's log for a signal before reporting "
        f"authorization_pending_timeout (default: {DEFAULT_WAIT_SECONDS})",
    )
    return parser


def _resolve_home(args: argparse.Namespace) -> Path:
    """Same flag > KEEL_HOME env > ~/.keel precedence keel-runtime's own config.py uses --
    resolved here (rather than left to each subprocess) so this script's own log-file placement
    and every subprocess invocation agree on the same directory regardless of ambient environment
    differences (contracts/skill-script-output.md's --home documentation)."""
    if args.home:
        return Path(args.home).expanduser()
    env_home = os.environ.get("KEEL_HOME")
    if env_home:
        return Path(env_home).expanduser()
    return Path.home() / ".keel"


# ------------------------------------------------------------------------------- runtime resolution


def resolve_runtime(args: argparse.Namespace) -> Optional[RuntimeLocation]:
    """spec FR-002 / research.md §1: a `keel` command on PATH wins whenever it exists (the
    eventual real-world, packaged case); only then fall back to --runtime-path/KEEL_RUNTIME_PATH,
    and only if that directory actually looks like a keel_runtime checkout."""
    keel_on_path = shutil.which("keel")
    if keel_on_path:
        return RuntimeLocation(argv_prefix=[keel_on_path], cwd=None)

    runtime_path = args.runtime_path or os.environ.get("KEEL_RUNTIME_PATH")
    if runtime_path:
        candidate = Path(runtime_path).expanduser()
        if (candidate / "keel_runtime" / "__main__.py").is_file():
            # sys.executable, not a bare "python3" looked up on PATH: this script is already
            # running under some Python interpreter, and re-using it is strictly more reliable
            # than assuming "python3" resolves to a compatible one (or resolves at all) in
            # whatever PATH the caller (Claude Code, a test harness) provides -- functionally
            # the same as the documented "invoked as python3 -m keel_runtime" shape.
            return RuntimeLocation(argv_prefix=[sys.executable, "-m", "keel_runtime"], cwd=candidate)

    return None


# ------------------------------------------------------------------------------------- status check


def run_status(location: RuntimeLocation, home: Path) -> Optional[dict]:
    """Invokes `<location> status --home <home>` and parses its documented spec-021 contract.
    Returns None on any failure to honor that contract -- a crash, non-zero exit, output that
    isn't exactly one JSON line, or JSON missing the required `running` key -- so the caller can
    report `internal_error` instead of letting an exception escape (spec FR-008)."""
    argv = location.argv_prefix + ["status", "--home", str(home)]
    try:
        completed = subprocess.run(
            argv,
            cwd=str(location.cwd) if location.cwd else None,
            capture_output=True,
            text=True,
            timeout=STATUS_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if completed.returncode != 0:
        return None

    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        return None

    try:
        data = json.loads(lines[0])
    except ValueError:
        return None

    if not isinstance(data, dict) or "running" not in data:
        return None

    return data


# --------------------------------------------------------------------------------- launching connect


def launch_connect(location: RuntimeLocation, home: Path, args: argparse.Namespace) -> tuple[int, Path]:
    """Launches `keel connect` detached (research.md §2) with its combined output redirected to
    a log file under `home` (spec FR-005). Returns the launched process's pid and the log path.
    Raises OSError if the subprocess cannot even be started (surfaced by the caller as
    `internal_error`, spec FR-008)."""
    home.mkdir(parents=True, exist_ok=True)
    log_path = home / LAUNCH_LOG_FILENAME

    argv = location.argv_prefix + ["connect", "--home", str(home)]
    if args.base_url:
        argv += ["--base-url", args.base_url]
    if args.executor:
        argv += ["--executor", args.executor]
    if args.credential_backend:
        argv += ["--credential-backend", args.credential_backend]
    if args.no_browser:
        argv += ["--no-browser"]

    popen_kwargs = {}
    if os.name == "posix":
        popen_kwargs["start_new_session"] = True
    else:  # pragma: no cover -- exercised on Windows only
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    with open(log_path, "w", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            argv,
            cwd=str(location.cwd) if location.cwd else None,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            **popen_kwargs,
        )
    # The child has already duplicated the fd -- closing our own handle above (the `with` block
    # exiting) does not stop it from writing.
    return process.pid, log_path


def _extract_value(content: str, prefix: str) -> Optional[str]:
    for line in content.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):]
    return None


def await_launch_signal(log_path: Path, wait_seconds: float) -> dict:
    """spec FR-006 / research.md §3-4: poll the launched process's log for a bounded time for
    either signal keel-runtime's own cli.py/auth.py already print. Returns an outcome dict
    without `pid`/`log_file` -- the caller fills those in, since this function only knows about
    the log."""
    deadline = time.monotonic() + wait_seconds
    while True:
        content = ""
        if log_path.exists():
            try:
                content = log_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                content = ""

        user_code = _extract_value(content, USER_CODE_PREFIX)
        verification_uri = _extract_value(content, VERIFICATION_URI_PREFIX)
        if user_code and verification_uri:
            return {
                "outcome": "authorization_started",
                "user_code": user_code,
                "verification_uri": verification_uri,
            }

        agent_session_id = _extract_value(content, AGENT_SESSION_ID_PREFIX)
        if agent_session_id:
            return {"outcome": "connected", "agent_session_id": agent_session_id}

        if time.monotonic() >= deadline:
            return {
                "outcome": "authorization_pending_timeout",
                "message": (
                    "keel connect did not report an authorization code or a connection within "
                    "the wait window; it may still be starting -- check the log file or try "
                    "again shortly."
                ),
            }

        time.sleep(LAUNCH_SIGNAL_POLL_INTERVAL_SECONDS)


# ------------------------------------------------------------------------------------------- output


def _emit(payload: dict, exit_code: int) -> int:
    print(json.dumps(payload))
    return exit_code


def _runtime_unavailable() -> int:
    return _emit({
        "outcome": "runtime_unavailable",
        "message": (
            "no 'keel' command found on PATH and no usable --runtime-path/KEEL_RUNTIME_PATH "
            "directory (expected <path>/keel_runtime/__main__.py inside it). Install "
            "keel-runtime once it is packaged (pip install keel-runtime), or point "
            "--runtime-path/KEEL_RUNTIME_PATH at a keel-cloud checkout's keel-runtime/ "
            "directory for development."
        ),
    }, 0)


def _internal_error(message: str) -> int:
    return _emit({"outcome": "internal_error", "message": message}, 1)


# --------------------------------------------------------------------------------------------- main


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    home = _resolve_home(args)

    location = resolve_runtime(args)
    if location is None:
        return _runtime_unavailable()

    status_result = run_status(location, home)
    if status_result is None:
        return _internal_error(
            "'keel-runtime status' did not return a well-formed answer (see "
            "keel-cloud specs/021-keel-runtime-status/contracts/status-cli-output.md) -- it "
            "may have crashed, printed something other than one JSON line, or omitted the "
            "required 'running' key."
        )

    if status_result.get("running") is True:
        return _emit({
            "outcome": "already_connected",
            "agent_session_id": status_result.get("agent_session_id"),
            "base_url": status_result.get("base_url"),
            "last_heartbeat_at": status_result.get("last_heartbeat_at"),
        }, 0)

    try:
        pid, log_path = launch_connect(location, home, args)
    except OSError as exc:
        return _internal_error(f"failed to launch 'keel connect': {exc}")

    outcome = await_launch_signal(log_path, args.wait_seconds)
    outcome["pid"] = pid
    outcome["log_file"] = str(log_path)
    return _emit(outcome, 0)


if __name__ == "__main__":
    sys.exit(main())
