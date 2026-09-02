---
description: "Task list for feature implementation"
---

# Tasks: Keel Connect Check (skill)

**Input**: Design documents from `/specs/001-keel-connect-check/`

**Prerequisites**: plan.md, spec.md, research.md, contracts/skill-script-output.md -- all present.

**Tests**: included -- this feature's entire value is a script's control-flow correctness; every
outcome branch is covered by a fast unit test against a fake runtime this repository controls.

**Organization**: three user stories in spec.md (P1, P1, P2); small enough that Foundational ->
per-story implementation-with-tests -> Polish covers it without further slicing.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

All paths are relative to the repository root, `~/Documents/projects/keel-connect-skill`.

---

## Phase 1: Foundational (blocking prerequisites)

- [X] T001 Create the repository skeleton: `scripts/`, `tests/`, `tests/fixtures/`, `.gitignore`
  (Python patterns: `__pycache__/`, `*.pyc`, `.venv/`), `AGENTS.md` (brief, mirroring
  `keel-runtime/README.md`'s and `keel-cloud/AGENTS.md`'s tone without copying their content).

- [X] T002 [P] Build the fake runtime fixtures both resolution branches will invoke:
  `tests/fixtures/fake_runtime_path/keel_runtime/__main__.py` (a `python3 -m keel_runtime` target,
  for the `--runtime-path` branch) and `tests/fixtures/fake_runtime_on_path/keel` (a standalone
  executable, `chmod +x`, for the `PATH` branch) -- both implementing the same small `status`/
  `connect` behavior, switched on one `FAKE_KEEL_SCENARIO` environment variable so tests fully
  control every outcome without touching a real `keel-runtime` or Keel Cloud. Scenarios needed:
  `already_connected` (status always reports running), `not_running_then_auth` (status reports not
  running; connect prints `KEEL_USER_CODE=`/`KEEL_VERIFICATION_URI=` then blocks),
  `not_running_then_instant_connect` (connect prints `KEEL_AGENT_SESSION_ID=` directly, no user
  code), `not_running_then_no_signal` (connect prints neither, just blocks -- exercises the timeout
  path), `status_crash` (status prints non-JSON and exits 1 -- exercises `internal_error`).

**Checkpoint**: fixtures runnable standalone (`python3 tests/fixtures/fake_runtime_on_path/keel
status`) before the real script exists.

---

## Phase 2: User Story 1 - nothing running yet (Priority: P1)

**Goal**: the script correctly launches `connect` detached and reports `authorization_started`,
`connected`, or `authorization_pending_timeout` depending on what the launched process's log shows
within the bounded wait.

### Implementation for User Story 1

- [X] T003 [US1] Create `scripts/keel_connect_check.py`: argument parsing (`--runtime-path`,
  `--base-url`, `--executor`, `--credential-backend`, `--no-browser`, `--home`, `--wait-seconds`,
  contracts/skill-script-output.md's Invocation section); `--home` resolution mirroring
  `keel-runtime/keel_runtime/config.py`'s flag > `KEEL_HOME` env > `~/.keel` precedence exactly;
  runtime resolution (`PATH` via `shutil.which("keel")`, else `--runtime-path`/`KEEL_RUNTIME_PATH`
  validated by checking `<path>/keel_runtime/__main__.py` exists, else `None` ->
  `runtime_unavailable`, research.md §1); `run_status()` invoking `<resolved> status --home <home>`
  via `subprocess.run(..., capture_output=True, text=True, timeout=15)`, parsing exactly one JSON
  line, returning `None` on any failure to honor spec 021's own contract (crash, bad JSON, missing
  `running` key) so the caller can report `internal_error` rather than propagate an exception.

- [X] T004 [US1] Extend `keel_connect_check.py`: when `status` reports not running, `launch_connect()`
  -- build the `connect` argv with `--home` always and the pass-through flags only when supplied;
  open `<home>/keel-connect-check.launch.log` for writing (creating `<home>` first);
  `subprocess.Popen(argv, cwd=<runtime cwd or None>, stdout=log_handle, stderr=subprocess.STDOUT,
  start_new_session=True)` (research.md §2); close the log handle in the parent immediately after
  `Popen` returns; return the launched pid and log path.

- [X] T005 [US1] Extend `keel_connect_check.py`: `await_launch_signal()` -- poll the log file every
  0.25s up to `--wait-seconds` (default 8.0, research.md §3), checking on each pass, in order: both
  `KEEL_USER_CODE=` and `KEEL_VERIFICATION_URI=` present -> `authorization_started`;
  `KEEL_AGENT_SESSION_ID=` present alone -> `connected` (research.md §4); deadline reached with
  neither -> `authorization_pending_timeout`. Every one of these three results carries `pid` and
  `log_file` (research.md §5, contracts guarantee #4).

- [X] T006 [P] [US1] Write `tests/test_keel_connect_check.py`'s Story 1 cases against
  `fake_runtime_path` (simplest resolution branch to hold fixed while varying scenario): scenario
  `not_running_then_auth` -> asserts `authorization_started` with the fixture's known code/URL, a
  live `pid`, and a `log_file` that exists and contains both marker lines (kill the pid in the
  test's cleanup, since the fixture blocks forever by design); scenario
  `not_running_then_instant_connect` -> asserts `connected` with the fixture's known
  `agent_session_id`; scenario `not_running_then_no_signal` with a short `--wait-seconds` (e.g. 1.0)
  -> asserts `authorization_pending_timeout` within a bounded test-time budget, and that the launched
  process is still alive (not killed just because the wait elapsed).

**Checkpoint**: all of Story 1's three acceptance scenarios pass against the fake runtime.

---

## Phase 3: User Story 2 - already connected (Priority: P1)

**Goal**: `status: running true` short-circuits to `already_connected` with zero launches.

### Implementation for User Story 2

- [X] T007 [US2] Extend `keel_connect_check.py`'s `main()`: when `run_status()` returns
  `running: true`, emit `already_connected` (with `agent_session_id`/`base_url`/`last_heartbeat_at`
  copied straight from `status`'s own answer) and return before any `launch_connect()` call is even
  reachable in the control flow.

- [X] T008 [P] [US2] Write `tests/test_keel_connect_check.py`'s Story 2 case: scenario
  `already_connected` -> asserts the JSON outcome and, using the fixture's own recorded-invocation
  mechanism (the fake writes a marker file the first time its `connect` subcommand is ever invoked),
  asserts that marker file was never created -- proving no redundant launch happened, not just that
  the JSON looked right.

**Checkpoint**: Story 2's acceptance scenario passes; SC-002 (no redundant launch) has a real
assertion behind it, not just an outcome-string check.

---

## Phase 4: User Story 3 - no runtime found (Priority: P2)

**Goal**: both resolution failure modes (`PATH` scrubbed and no override; a `--runtime-path` pointed
at a directory with no `keel_runtime` package) report `runtime_unavailable` cleanly.

### Implementation for User Story 3

- [X] T009 [US3] Verify (no new production code expected beyond T003's resolution logic already
  covering this) that an unresolved runtime short-circuits before any subprocess is spawned at all --
  `run_status`/`launch_connect` must not be reachable in this path.

- [X] T010 [P] [US3] Write `tests/test_keel_connect_check.py`'s Story 3 cases: invoke the script as a
  subprocess with `PATH` set to a directory containing no `keel` executable and `KEEL_RUNTIME_PATH`
  unset/empty -> asserts `runtime_unavailable`, exit 0; invoke with `--runtime-path` pointed at an
  empty temp directory (no `keel_runtime/` inside it) -> same assertion, proving the validation check
  (not just "the directory exists") is what gates this branch.

- [X] T011 [P] [US3] Write `tests/test_keel_connect_check.py`'s `internal_error` case (not its own
  user story in spec.md, but the one non-zero-exit path FR-008 requires coverage for): scenario
  `status_crash` against `fake_runtime_path` -> asserts `{"outcome": "internal_error", ...}` and exit
  code **1**, the only test in this suite asserting a non-zero exit.

**Checkpoint**: all outcomes in `contracts/skill-script-output.md` are covered by at least one test;
`python3 -m unittest discover tests -v` is fully green.

---

## Phase 5: Polish & cross-cutting concerns

- [X] T012 [P] Write `SKILL.md` at the repository root: frontmatter (`name: "keel-connect"`,
  `description` stating the trigger -- the user typing or clearly meaning "keel connect" -- per the
  shape of `keel-cloud/.claude/skills/speckit-implement/SKILL.md`'s frontmatter, adapted for a
  single always-available skill rather than a spec-kit slash command); body instructing Claude to
  run `scripts/keel_connect_check.py` (path resolved relative to this file's own directory) with no
  flags by default, and how to phrase each of the six documented outcomes to a human, including
  relaying `user_code`/`verification_uri` verbatim and mentioning the user can ask again later to
  confirm.

- [X] T013 [P] Write `README.md`: what this skill does, how to run its script and its tests
  manually, and an explicit pointer to `contracts/skill-script-output.md` as the one contract other
  code depends on -- plus a one-line pointer to the separate `keel-cloud`
  `KeelConnectSkillJourneyTest` as the real three-tier proof this repository's own tests don't
  attempt.

- [X] T014 Run `python3 -m unittest discover tests -v` until green; fix any timing flakiness in the
  timeout-path test (T006) by keeping `--wait-seconds` short in that test rather than sleeping longer
  in the test itself.

- [X] T015 `git init`, an initial commit covering every file above.

---

## Dependencies & Execution Order

- **Phase 1 (T001-T002) blocks everything** -- the fixtures are what every later test invokes.
- **T003 blocks T004/T005** (same file, sequential edits to one script) -- do them as one continuous
  pass rather than true parallel tasks, despite not being marked `[P]` against each other.
- **T006, T008, T010, T011 can all run in parallel with each other** once T003-T005/T007/T009 land
  (each writes to the same test file but covers a disjoint scenario -- write them as one pass through
  the file rather than literally parallel edits, to avoid a trivial merge conflict with yourself).
- **T012-T013 (Polish) can start any time the contract is stable** -- they describe behavior, not
  implementation, so they don't block on T003-T011 landing first, only on the contract file (already
  written) not changing further.
- **T014-T015 after everything above.**

## Implementation Strategy

**MVP = the whole feature** -- three small user stories over one script, small enough that no
incremental delivery slicing beyond the phases above adds value. Foundational fixtures first
(nothing else is testable without them), then each story's script logic and its own tests together,
then polish.
