#!/usr/bin/env python3
"""A fake `keel_runtime` from **before** `keel disconnect` existed.

Its whole reason to exist is one line it does *not* have: there is no `disconnect` subparser, so a
`disconnect` invocation is a real `argparse` failure -- usage on stderr, exit 2 -- and the skill's
`internal_error` path for "your keel-runtime predates this command" is exercised against the thing
that actually happens rather than a mock of it (keel-cloud `canon/designs/keel-disconnect-design.md`
§8.2).

`status` and `connect` are the two subcommands every runtime has always had, kept here only so this
fixture resolves and answers like a runtime rather than like a broken file.
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
    args = build_parser().parse_args(list(sys.argv[1:] if argv is None else argv))

    if args.command == "status":
        print(json.dumps({
            "running": False,
            "home": args.home or os.environ.get("FAKE_KEEL_HOME"),
            "base_url": "http://old-runtime.test",
            "environment": "old-runtime.test",
        }))
        return 0

    while True:  # a real `connect` never returns on its own
        time.sleep(0.2)


if __name__ == "__main__":
    sys.exit(main())
