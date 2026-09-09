---
description: "Task list for feature implementation"
---

# Tasks: The runtime travels inside the skill

**Input**: [spec.md](spec.md), [plan.md](plan.md), keel-cloud
`canon/designs/keel-skill-design.md` §13 step 3.

**Tests**: included. This feature's value is a script's control flow plus a resolution order, and
both are only true if something ran them; the order in particular is the kind of rule that reads
correct and behaves backwards.

**Organization**: one foundational phase (the build step and the shared module, which everything
else needs), then the five user stories, then the words. All paths are relative to the repository
root.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Foundational (blocking prerequisites)

- [X] T001 `Makefile` with `make runtime`: copy `$(KEEL_RUNTIME_SRC)/keel_runtime/` in, strip
  `__pycache__`, stamp `RUNTIME_VERSION`. Refuse a source that is not a git checkout, has no HEAD,
  or is dirty (FR-001, FR-002, D2). Plus `make test` (with a `PYTHON` override, so the floor is one
  word away) and `make clean`.

  *Found on the way*: keel-runtime has no tags at all, so the design's `RUNTIME_VERSION: v0.2.0`
  example cannot be produced yet. `make runtime` writes the exact tag when there is one and
  `<__version__>+<short sha>` otherwise -- `0.1.0+8dacbbf` today.

- [X] T002 `.gitignore`: `/keel_runtime/`, rooted, with the comment saying why (FR-003). Rooted
  matters -- an unanchored `keel_runtime/` would also have swallowed the fake runtime fixture under
  `tests/`, which is committed and must be.

- [X] T003 `scripts/_runtime_location.py`: `RuntimeLocation`, `skill_root()`, `resolve_runtime()`
  with §3.2's three rules and its `source` labels, `child_env()` (prepend to `PYTHONPATH`), and
  `run_capturing()` (FR-004, FR-005, FR-013). `environ` and `which` are injectable so the branches
  can be unit-tested without a machine that happens to have a `keel`.

  *Found on the way*: `python3 -m <pkg>` prepends the **working directory** to `sys.path`, ahead of
  `PYTHONPATH`. Measured on `/usr/bin/python3` 3.9.6: a `PYTHONPATH` pointing at a fake runtime was
  ignored entirely in favour of a `keel_runtime/` sitting in `cwd`. `PYTHONSAFEPATH=1` fixes it
  exactly and is 3.11+, so `child_env()` sets it **and** `child_cwd()` roots the module branch in
  the directory it resolved. This is the one deviation from §3.2, and it is documented in the
  module's own docstring beside the measurement.

**Checkpoint**: `make runtime` produces a `keel_runtime/` byte-identical to the source (verified by
`diff -r`, `__pycache__` aside) and `RUNTIME_VERSION` names its commit.

---

## Phase 2: User Story 2 - the version gate (Priority: P1)

Done first among the stories, because everything below it in the file depends on the file parsing.

- [X] T004 [US2] The gate at the top of `scripts/keel_connect_check.py`: first executable
  statement, above every import but `sys`, one line of JSON, exit 0, per-OS install command
  (FR-006, X-3). And the whole file rewritten to syntax every Python 3 parses -- `%` formatting
  instead of f-strings, no `from __future__ import annotations` (which cannot be there anyway: the
  gate must come first), no annotations.

- [X] T005 [US2] `VersionGateTestCase`: a runner that overwrites `sys.version_info` and
  `sys.platform` and executes the real file through `runpy`. Four cases -- the shape and exit code,
  the three per-OS clauses, that 3.9 itself does not trip it, and that a perfectly good runtime
  sitting right there does not change the answer.

---

## Phase 3: User Story 1 + 3 - resolution (Priority: P1/P2)

- [X] T006 [US1] `main()` rewritten around `_runtime_location`: resolve, `status`, launch, wait.
  `runtime_unavailable`'s message rewritten to name neither a package index nor the development
  override (FR-015, X-4), and `--runtime-path`'s help set to `argparse.SUPPRESS`.

- [X] T007 [P] [US1] `ResolutionOrderTestCase`: unit cases for all three `source` labels and for
  `child_env`, and six end-to-end cases run from **relocated copies of the skill** built by
  `make_skill_root()` -- because the bundled branch resolves relative to `scripts/`'s parent, and
  testing it with a flag pointing back at this repository would test nothing.

  *Found on the way*: the two fake runtimes had identical behaviour, so a test offering both a
  bundled copy and a `keel` on `PATH` could not say which had answered. The on-`PATH` fixture now
  names a different Keel by default (`stranger-keel.test`), so the `environment` in the outcome is
  the assertion and there is no way to read it the wrong way round.

- [X] T008 [US3] The checkout rule, and its two failure modes: a `--runtime-path` that is not a
  runtime falls through rather than failing, and `KEEL_RUNTIME_PATH` works where the flag does.
  Plus the X-4 grep over the one message a founder can reach.

---

## Phase 4: User Story 4 - the host (Priority: P2)

- [X] T009 [US4] `--host {claude,copilot,auto}`, `detect_host()` over the four variables, and
  `executor_for()` -- explicit `--executor` first, then an explicit host, then the table, then
  nothing (FR-007, FR-008). `HOST_EXECUTORS` maps `claude` to `claude-code`, the permanent accepted
  alias (C-12) and the only one of the two names today's runtime knows.

- [X] T010 [P] [US4] `HostDetectionTestCase`: the table as twelve cases over a dict, including both
  "two different answers mean no answer" rows; explicit beating detected; the executor reaching
  `connect`'s argv; nothing reaching `status`; and the outcome's key set unchanged when a host was
  detected (decision 15).

  *Found on the way*: asserting flag passthrough needed the fakes to record what they were asked
  to run. Both now write the whole `connect` argv to `<home>/connect-argv.json`, which also made
  the `--home`-only-when-given rule (T011) directly assertable rather than inferred.

---

## Phase 5: User Story 5 - which Keel (Priority: P2)

- [X] T011 [US5] `environment` on all seven shapes from the one `_emit`; `null` exactly when no
  runtime answered; `already_connected` loses `base_url` (FR-009, FR-010). `--home` passed only
  when given, and the launch log written to the home `status` named (FR-011). The fakes grew
  `home`/`base_url`/`environment`/`executor`/`executor_on_path` in both status shapes to match the
  runtime, plus a `status_without_environment` scenario for the older-runtime case.

- [X] T012 [P] [US5] `OutcomeTestCase`, and the guarantee assertions moved into the harness: every
  `run_script` call, in every class, asserts one JSON line, the right exit code, and `environment`
  present -- so those three cannot be forgotten by a case written later.

---

## Phase 6: The words, and the floor

- [X] T013 `specs/001-keel-connect-check/contracts/skill-script-output.md` rewritten in place for
  seven shapes, with the "what changed from spec 001's six" table at the end (FR-016).

- [X] T014 `SKILL.md`: seven replies, the `environment` clause every reply ends with, the Python
  clause for a machine with no `python3` at all, and the one host line marked as the D5 exception
  (FR-014). Frontmatter deliberately untouched -- see plan.md.

- [X] T015 [P] `README.md` and `AGENTS.md` brought level: the runtime travels inside, the
  prerequisite paragraph in the second of its three places, the real resolution order, and the
  rules a future agent must not break.

- [X] T016 `.github/workflows/tests.yml`: 3.9-3.13 on Linux plus both ends on macOS and Windows,
  staging the runtime with `make runtime` from a real clone of keel-runtime (T-1) and installing
  neither `keyring` nor `jsonschema` (R-2), with a final step that runs the script with no flag at
  all (FR-012).

- [X] T017 The floor, run: the whole suite green on `/usr/bin/python3` 3.9.6 and on the newest
  interpreter present, and one real run against the playground keel-cloud.

**Checkpoint**: 36 tests green on 3.9.6, 3.12.5 and 3.13.13.

---

## What is deliberately not here

`make dist`, `VERSION`, `packaging/` and the four trees are spec `004-skill-packaging`, including
L1's byte-for-byte comparison of `keel_runtime/` against keel-runtime at `RUNTIME_VERSION` -- the
test that makes D2 enforceable rather than merely stated. `scripts/keel_disconnect.py` is spec
`002-keel-disconnect`; `_runtime_location.py` is already shaped for it and it will use it whole.
`--executor copilot` needs keel-runtime's spec `005-copilot-executor`; the skill sends the name
today and the runtime will reject it until then.
