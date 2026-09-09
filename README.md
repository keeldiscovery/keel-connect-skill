# keel-connect-skill

An agent skill: when a user says or clearly means "keel connect", check whether a local Keel
runtime is already running and connected to Keel Cloud, and if not, start it for them and hand back
the code and URL they need to approve the device.

**The runtime travels inside the skill.** `keel_runtime/` is copied in from the
[keel-runtime](../keel-runtime) repository by `make runtime` and ships beside
`scripts/keel_connect_check.py`; the script runs it with the interpreter that ran the script.
Nothing is downloaded, nothing is installed, and there is no binary, manifest, checksum or
signature anywhere in this design.

**The one prerequisite is Python 3.9 or newer.** 3.9 is the floor because Apple's command-line
tools ship 3.9.6; Debian 11 ships 3.9 and everything newer clears it. A user on an older Python
gets one sentence naming the install command for their operating system, rather than a
`SyntaxError`. A user with no `python3` at all cannot be told anything by a script that cannot
start -- the command just fails -- so the answer is written down where a human will find it, this
being one of three such places:

> Keel needs Python 3.9 or newer, installed once. On macOS: `xcode-select --install`, or
> https://www.python.org/downloads/. On Windows: `winget install Python.Python.3.12`, or Python
> from the Microsoft Store. On Linux: your package manager, e.g. `sudo apt install python3`.

The design of record is keel-cloud `canon/designs/keel-skill-design.md`.

## Layout

- `SKILL.md` -- trigger condition and outcome-interpretation instructions for the agent host.
- `scripts/keel_connect_check.py` -- the whole implementation. Stdlib-only Python, invoked as a
  subprocess, printing one line of JSON.
- `scripts/_runtime_location.py` -- the resolution order, shared by every script in this skill.
- `keel_runtime/` -- **generated, gitignored**, written by `make runtime`. There is one copy of the
  runtime's source in the world and it is in keel-runtime; every copy here is made by a build step
  from one named commit.
- `RUNTIME_VERSION` -- committed: which keel-runtime this skill carries.
- `specs/` -- the design docs: `001-keel-connect-check` (the original script, and the output
  contract, which lives there and is rewritten in place) and `003-bundled-runtime` (this one).
- `tests/` -- this repository's own tests: fast, offline, mostly against fake runtimes in
  `tests/fixtures/`, plus a handful against the real bundled runtime.

## Getting it ready

```sh
make runtime          # copies ../keel-runtime/keel_runtime/ in and stamps RUNTIME_VERSION
make test             # python3 -m unittest discover tests -v
```

`make runtime` refuses if the sibling checkout is dirty or is not on a commit: `RUNTIME_VERSION`
must be able to name exactly what was copied. Point it elsewhere with
`make runtime KEEL_RUNTIME_SRC=<path>`, and run the tests on another interpreter with
`make test PYTHON=/usr/bin/python3`.

`make dist` and the four packaging trees (a Claude Code plugin, a Spec Kit extension, a bare
installer, a Copilot repo drop) are spec `004-skill-packaging`, not this one.

## Running the script by hand

```sh
python3 scripts/keel_connect_check.py
# {"outcome": "authorization_started", "user_code": "...", "verification_uri": "...", ...}
```

One of seven outcomes: `already_connected`, `connected`, `authorization_started`,
`authorization_pending_timeout`, `runtime_unavailable`, `python_too_old`, `internal_error`. Exactly
one line of JSON, exit 0 for all of them except `internal_error`. The exhaustive, stable contract
is `specs/001-keel-connect-check/contracts/skill-script-output.md`.

Which runtime runs, in order: a checkout named by `--runtime-path`/`KEEL_RUNTIME_PATH` (a
development override), then the `keel_runtime/` that travelled with this skill, then a `keel` on
`PATH`. **The bundled copy beats a `keel` on `PATH`** -- it is the runtime this skill's own tests
ran against, and a stranger's install must not shadow it silently.

## Running the tests

```sh
python3 -m unittest discover tests -v
```

Every outcome branch, the version gate under a faked old interpreter, all three resolution rules
and their order, the host-detection table, and the real bundled runtime answering from an empty
home. Offline, and no real Keel Cloud server anywhere -- the one network-shaped thing is a
`connect` launched at a closed local port, which is exactly what `authorization_pending_timeout`
looks like.

## The real three-tier proof lives elsewhere

This repository proves the script's own logic. The real end-to-end chain -- this script, launching
a real runtime, talking to a real Keel Cloud -- is `KeelConnectSkillJourneyTest` in the `keel-cloud`
repository, which shells out to `scripts/keel_connect_check.py` directly against a live
Testcontainers-backed Keel Cloud and a real runtime subprocess it launches.

## Dependencies

None beyond the Python standard library, matching the runtime's own posture. `keyring` and
`jsonschema` remain optional accelerators the runtime uses only if they happen to be importable;
nothing here installs them, and the behaviour tested is the behaviour without them.
