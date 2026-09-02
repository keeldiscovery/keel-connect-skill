# AGENTS.md

Instructions for AI coding agents (and humans) working in this repository.

## What this is

A Claude Code skill (`SKILL.md` + `scripts/keel_connect_check.py`) that checks whether a local
`keel-runtime` process is connected to Keel Cloud, and starts `keel connect` if not. It only
understands the keel runtime -- it has no relationship to `keel-discovery` (the unrelated,
MCP-hosted skill in the sibling `keel-skill` repository) beyond sharing a product name. Do not
model changes here on that skill's "zero shell access" constraint; it does not apply here.

## Before changing anything

Read `specs/001-keel-connect-check/spec.md` and `plan.md` first, and
`specs/001-keel-connect-check/contracts/skill-script-output.md` in particular -- that file is the
one thing another repository (`keel-cloud`'s `KeelConnectSkillJourneyTest`) depends on. A change to
any JSON shape it documents is a breaking change to that test, not a free implementation detail.

## Running things

```sh
python3 -m unittest discover tests -v      # this repository's own tests (fast, offline)
python3 scripts/keel_connect_check.py --runtime-path <path>/keel-runtime   # manual run
```

No build step, no dependency install -- everything here is stdlib-only Python and Markdown.

## Scope discipline

This repository does not implement, vendor, or duplicate any part of `keel-runtime` or Keel Cloud
itself -- it only shells out to `keel-runtime status`/`connect` and parses their documented output.
If a change here starts needing to know something about a job's request/response shape, workflow
state, or the discovery protocol, that is a sign the change belongs in `keel-cloud`, not here.
