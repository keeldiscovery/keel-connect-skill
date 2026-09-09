# AGENTS.md

Instructions for AI coding agents (and humans) working in this repository.

## What this is

An agent skill (`SKILL.md` + `scripts/`) that checks whether a local Keel runtime is connected to
Keel Cloud and starts it if not -- **carrying that runtime inside itself**. It only understands the
local runtime process; it has no relationship to Keel's discovery protocol, to MCP, or to any other
Keel-branded skill beyond sharing a product name.

## Before changing anything

Read, in this order:

1. keel-cloud `canon/designs/keel-skill-design.md` -- **the design of record**. Every rule here
   carries an invariant id (X-*, D-*, E-*) from its §9, and code comments cite those ids.
2. `specs/003-bundled-runtime/spec.md` and `plan.md` -- the current shape of this repository.
3. `specs/001-keel-connect-check/contracts/skill-script-output.md` -- **the one thing another
   repository depends on** (`keel-cloud`'s `KeelConnectSkillJourneyTest`). A change to any JSON
   shape it documents is a breaking change to that test, and a major version bump of this skill.
   It is the only thing that can be one.

## Running things

```sh
make runtime                          # copy the runtime in; required before anything works
make test                             # python3 -m unittest discover tests -v
make test PYTHON=/usr/bin/python3     # the 3.9 floor, which every change must also pass
python3 scripts/keel_connect_check.py # a manual run
```

No dependency install -- everything here is stdlib-only Python and Markdown.

## Rules that are not negotiable

- **`keel_runtime/` is generated, never committed** (D2). One copy of the runtime's source exists
  in the world and it is in keel-runtime. Do not hand-edit the copy here; edit it there and re-run
  `make runtime`.
- **The floor is Python 3.9** (§4). `scripts/keel_connect_check.py` must parse on *any* Python 3,
  because its version gate has to run before a `SyntaxError` can happen -- so no f-strings, no
  `from __future__ import annotations`, no walrus, no variable annotations anywhere in that file.
  The gate is the first executable statement, above every import but `sys` (X-3).
- **The development override stays invisible** (X-4). `--runtime-path`/`KEEL_RUNTIME_PATH` exist
  for developers and for keel-e2e-eval. No founder-facing message and no line of `SKILL.md` may
  name either.
- **The skill carries no address** (X-5). It never hard-codes a base URL, never builds or corrects
  a `verification_uri`, and reports the `environment` the runtime handed it -- or nothing.
- **No host name in a reply** (D5). `SKILL.md` carries exactly one deliberate exception, marked
  with an HTML comment saying so.

## Scope discipline

This repository does not implement or duplicate any part of the runtime or of Keel Cloud -- it
shells out to `status`/`connect` and parses their documented output. If a change here starts
needing to know something about a job's request/response shape, workflow state, or the discovery
protocol, that is a sign the change belongs in `keel-runtime` or `keel-cloud`, not here.
