# Feature Specification: Upgrade in place — "keel connect" replaces an older runtime

**Feature Branch**: `005-upgrade-in-place`

**Created**: 2026-09-11

**Status**: Implemented

**Input**: the founder, 2026-09-11 — *"how about we simplify that whenever a user types keel
connect the old runtime should be killed and new one should start … even if the other runtime
may have started in another CLI session"* — with the guard settled the same hour: replace only
when the bundle is newer and the runtime is idle, never a downgrade (Spec Kit installs the tree
per project, so one machine can hold two versions), and say so. Design of record: keel-cloud
`canon/designs/upgrade-in-place-design.md`; the runtime's half is keel-runtime spec
`007-launcher-version`.

## Scope

- **FR-001** The skill's `VERSION` file travels in every packaging (`SKILL_FILES`), and the
  connect check reads it as the bundle's version. A tree without it never upgrades anything.
- **FR-002** Every `connect` the check launches carries `--launcher-version <VERSION>`.
- **FR-003** With a runtime running and connected, the check compares the bundle's version with
  the runtime's `launcher_version` (an unknown one counts as older):
  - bundle newer, `busy: false` → **`upgraded`**: the runtime's own `disconnect` (the goodbye,
    the process, the proof it is gone), then this bundle's `connect`; the outcome carries
    `previous_version`, `bundle_version`, and `then` with the relaunch's own outcome and keys;
  - bundle newer, `busy: true` → **`upgrade_waiting`**: nothing stopped, nothing started;
  - otherwise → `already_connected`, now carrying `launcher_version`.
- **FR-004** `SKILL.md` names the two outcomes and their sentences; the contract
  (`specs/001-keel-connect-check/contracts/skill-script-output.md`) is amended; per design §7 a
  contract change is a major version, so the skill is **2.0.0**.
- **FR-005** A disconnect that does not answer stopped / not running / stale pid cleared is
  `internal_error`, and nothing is launched.

**Out of scope**: a runtime that is busy for longer than a founder is willing to wait (the
founder's word is "keel disconnect", as before); a version check on `disconnect`.

## Tests

`tests/test_keel_connect_check.py` (the six cases: older idle → upgraded; unknown launcher →
upgraded; older busy → waiting; newer running → kept; same version → already connected; a fresh
launch names the launcher), `tests/test_dist.py` (VERSION in every tree), and keel-e2e-eval's
S-013 for the real thing.
