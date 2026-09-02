# Implementation Plan: Keel Connect Check (skill)

**Branch**: `001-keel-connect-check` | **Date**: 2026-09-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-keel-connect-check/spec.md`

## Summary

A Claude Code skill with one deterministic, stdlib-only Python helper script
(`scripts/keel_connect_check.py`) that shells out to `keel-runtime status` (keel-cloud spec 021)
first, and only launches a detached `keel connect` (keel-cloud spec 020) when nothing is already
running -- watching the launched process's log for a bounded time for the human-facing signal lines
`cli.py`/`auth.py` already print, then reporting one of six stable JSON outcomes
(`contracts/skill-script-output.md`). `SKILL.md` is a thin instruction layer: when to invoke the
script, and how to phrase each outcome to a human. No other code exists in this repository.

## Technical Context

**Language/Version**: Python >= 3.10, standard library only -- matches `keel-runtime`'s own posture
(keel-cloud spec 020 FR-025) so the script runs on a bare `python3` with nothing installed, since
Claude Code invokes it as a plain subprocess.

**Primary Dependencies**: none. `argparse`, `json`, `os`, `pathlib`, `shutil`, `subprocess`, `time`.

**Storage**: none of this repository's own -- the script reads/writes nothing persistent itself; it
only redirects a launched `connect` process's stdout to a log file under the *runtime's* resolved
`$KEEL_HOME` (a path this script computes using the exact same precedence `keel-runtime` uses, but
owns no state of its own beyond that transient log).

**Testing**: `python3 -m unittest discover tests`, entirely against a fake runtime this repository
ships in `tests/fixtures/` -- two fixture shapes (a `keel_runtime/` package directory for the
`--runtime-path` resolution branch, and a standalone `keel` executable for the `PATH` resolution
branch), both driven by one `FAKE_KEEL_SCENARIO` environment variable so the same small fake logic
covers every outcome branch without needing a real `keel-runtime` install or a real Keel Cloud
server anywhere in this repository's own test run.

**Target Platform**: macOS/Linux primary (POSIX `start_new_session` for the detached launch); no
Windows-specific detached-process handling is implemented in this pass (documented as a known gap in
README.md, matching the honesty of keel-runtime's own Windows `pid_alive` fallback in spec 021).

**Project Type**: single small Python script plus a Markdown skill file -- no server, no persistence
layer, no build step. This is intentionally the smallest shape a Claude Code skill with real shell
access can take.

**Performance Goals**: the `status` check itself must be fast (bounded by `keel-runtime status`'s
own <100ms contract, spec 021 SC-001, plus one subprocess-spawn overhead); the worst case for a
`connect` launch is the configured `--wait-seconds` (default 8s) before `authorization_pending_timeout`
-- SC-001's "roughly ten seconds" ceiling.

**Constraints**: no dependency beyond the stdlib (FR-009); must never block indefinitely (FR-006);
must never leave a launched `connect` process's lifetime tied to the script's own (FR-004); must
never let a malformed/crashing `status` answer propagate as an unhandled exception (FR-008).

**Scale/Scope**: one script (~150-200 lines), one `SKILL.md`, one small test module plus fixtures.
No incremental slicing needed -- this whole feature is one script's control flow.

## Constitution Check

*GATE: no formal constitution file exists yet in this brand-new repository (no
`.specify/memory/constitution.md`) -- there is nothing to check against beyond spec.md's own stated
Scope. The principles that apply, stated informally since there is no formal document to cite:*

| Principle (informal, from spec.md's Scope) | How this feature satisfies it |
|---|---|
| **This skill only understands the keel runtime** | The script and `SKILL.md` reference nothing about Keel's discovery protocol, MCP, or the unrelated `keel-discovery` skill in `keel-skill` -- verified by grep during review: no such term appears anywhere in this repository. |
| **No shared code with `keel-discovery`'s "zero shell access" constraint** | Not applicable and not modeled -- this skill runs inside Claude Code with real Bash access; `keel-discovery`'s MCP-hosting constraint is specific to *its* hosting context, not this one, and spec.md's Scope says so explicitly. |
| **Stable contracts, not shared code, bridge repositories** | This script depends on keel-cloud spec 021's documented JSON contract only (parsed, never re-derived); its own output is likewise a documented contract (`contracts/skill-script-output.md`) other code (the `keel-cloud` E2E test) depends on the same way -- no shared library, no vendored code, no cross-repo import. |

No Complexity Tracking entry needed -- nothing here departs from the smallest reasonable shape for
this feature.

## Project Structure

### Documentation (this feature)

```text
specs/001-keel-connect-check/
├── spec.md
├── plan.md                          # this file
├── research.md
├── contracts/
│   └── skill-script-output.md
└── tasks.md
```

No `data-model.md` or `quickstart.md`: this feature's only "entity" is the single JSON outcome
object, already fully specified by `contracts/skill-script-output.md` -- a separate data-model
document would only restate it. No `quickstart.md` either -- `README.md` at the repository root
already carries the equivalent "run it, see it work" walkthrough for a project this small, and the
real end-to-end walk (script + real runtime + real Cloud) is the `keel-cloud` E2E test's job, not a
manual doc here. This is the judgement call spec.md's parent instructions explicitly allow ("smaller
than spec 021, so it may not need every optional artifact").

### Source code (repository root)

```text
keel-connect-skill/
├── SKILL.md                          # NEW: trigger + interpretation instructions for Claude
├── scripts/
│   └── keel_connect_check.py         # NEW: the entire helper script (spec's one real component)
├── tests/
│   ├── test_keel_connect_check.py    # NEW: all outcome branches, PATH-vs-runtime-path resolution,
│   │                                  # bounded-wait timeout, against the fake runtime below
│   └── fixtures/
│       ├── fake_runtime_path/
│       │   └── keel_runtime/
│       │       └── __main__.py       # NEW: fake runtime, `--runtime-path` resolution branch
│       └── fake_runtime_on_path/
│           └── keel                  # NEW: fake runtime, `PATH` resolution branch (executable)
├── README.md                          # NEW
├── AGENTS.md                          # NEW
├── .gitignore                         # NEW
└── specs/001-keel-connect-check/      # this feature's design docs (above)
```

**Structure Decision**: flat, single-purpose repository -- no `src/` layer, no package to install
(the script is invoked directly by path, per `SKILL.md`'s instructions, exactly as `keel-runtime`
itself is invoked uninstalled by `KeelConnectJourneyTest` in `keel-cloud`). This mirrors the
smallest-viable shape of `keel-runtime` itself (spec 020) scaled down further, since this repository
has no package-import surface to expose -- only one script ever gets executed, never imported.

## Complexity Tracking

*No Constitution Check violations -- table not needed.*
