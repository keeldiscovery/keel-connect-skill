# Tasks: There is a door out

**Branch**: `002-keel-disconnect` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Design of record**: keel-cloud `canon/designs/keel-disconnect-design.md` §10 step 5.

## Format: `[ID] [P?] [Story] Description`

`[P]` = may run in parallel with the task before it (different files, no dependency).
`[US*]` = the user story in `spec.md` it serves.

---

## Phase 1: The contract, first

- [X] T001 `specs/002-keel-disconnect/contracts/skill-disconnect-output.md`: the six shapes, the
  eight guarantees, the invocation, which runtime runs, and the table mapping the runtime's four
  names onto four of the six (FR-005, FR-011). Written before the script, because the script's
  only job is to honour it. The `--home` deviation from the design's §5.2 is named here, with the
  reason, rather than left for a reader to notice.

## Phase 2: The script (Priority: P1) -- US1, US2, US3, US4

- [X] T002 [US1] `scripts/keel_disconnect.py`: `build_parser` (`--home`, and `--runtime-path`
  suppressed from `--help` per X-4), `resolve_given_home` mirroring the connect script's rule
  exactly (FR-003), `run_disconnect` invoking the resolved runtime and parsing its contract,
  `translate` mapping four outcomes onto four (FR-005, FR-007), `_emit` as the one place every
  shape is printed (FR-004), `_runtime_unavailable` and `_internal_error` (FR-010). Stdlib only,
  pre-3.9 syntax, no launch path anywhere in the file (FR-008), no network and no credential
  (FR-009).

- [X] T003 [US4] The `internal_error` messages, each naming its own cause: a non-zero exit that
  names the missing `disconnect` subcommand and the update as its remedy; output that is not one
  JSON line; output that is not JSON; a missing `outcome`; an `outcome` this skill does not know
  ("it may be newer than this skill"). One sentence each -- "something went wrong" is not a
  remedy (FR-010).

## Phase 3: The fixtures (Priority: P1)

- [X] T004 [US1][US2][US3] A `disconnect` subcommand on **both** existing fake runtimes, driven by
  the same `FAKE_KEEL_SCENARIO` variable: `stopped`, `stopped_sigkill`, `not_running` (the
  default), `stale_pid`, `timeout`, `disconnect_crash`, `disconnect_two_lines`,
  `unknown_outcome`. Each shape carries the three address keys the runtime's contract puts on all
  four of its own, and the invocation records its argv to `disconnect-argv.json` so a test can
  assert exactly what was passed.

- [X] T005 [P] [US4] `tests/fixtures/fake_runtime_no_disconnect/`: a runtime with `status` and
  `connect` and **no `disconnect` subparser**, so the old-runtime path into `internal_error` is a
  real `argparse` exit 2 with usage on stderr rather than a mock of one (design §8.2).

## Phase 4: The tests (Priority: P1)

- [X] T006 `tests/test_keel_disconnect.py::DisconnectHarness`: the scratch directory, the relocated
  skill root a packaging produces, and one `run_script` that asserts the contract's hard guarantees
  before returning -- one JSON line, the exit-code rule, `environment` present, and the
  **documented key set exactly**, in both directions (guarantees 1, 2, 5, 6).

- [X] T007 [US1][US2][US3] `OutcomeTestCase`: every one of the six outcomes, each run through
  **both** resolution branches -- the runtime bundled beside a relocated skill, and a `keel` on
  `PATH` with no bundled runtime. The two fixtures name different Keels, so the `environment` in
  the answer says which one actually ran (FR-015).

- [X] T008 [P] `NeverStartsAnythingTestCase`: S3 twice over -- the absence of the fixtures' own
  `connect-was-invoked` marker after every outcome, and a source assertion that there is no
  `Popen`, no `start_new_session` and no `"connect"` argv anywhere in the file (FR-008).

- [X] T009 [P] `HomeTestCase`: `--home` passed when given, `KEEL_HOME` counting as given, the flag
  beating the environment, nothing passed when nothing was given -- and one unit case asserting
  `resolve_given_home` answers identically in both scripts, so the two files cannot drift apart
  quietly (FR-003).

- [X] T010 [P] `TranslationTestCase`: `translate` alone -- the four names, the exact key set of each
  shape, `home` and `base_url` deliberately not coming up, and an `environment` the runtime did not
  name reported as `null` rather than guessed (FR-006, FR-007).

- [X] T011 [US1] `RealDisconnectTestCase`: the real bundled runtime, a real `keel connect` through
  the **sibling script** against a live keel-cloud, the founder's browser click stood in for over
  HTTP, then `disconnected` -- pid observed not alive, heartbeat gone, `SIGTERM` -- then
  `not_running`, then the credential still present (D7). Skips itself when no keel-cloud is
  listening, so the suite stays offline by default (FR-015).

## Phase 5: The words

- [X] T012 `SKILL.md` frontmatter: `name`, `description`, `license` and nothing else; the
  description rewritten trigger-first, carrying **both** jobs' phrasings; `user-invocable` and
  `disable-model-invocation` dropped (FR-013, skill design decisions 5 and 6). Measured: 449
  characters of description inside 514 of frontmatter, against limits of 500 and 1,024.

- [X] T013 [US5] `SKILL.md` body: *Two jobs, and which is which* before either script's section,
  carrying the ambiguity rule in the design's own words (S1); *Running the disconnect*;
  *Interpreting each disconnect outcome*, six replies; *What "keel connect" says right after a
  disconnect*, all three windows including the one that is accepted and named; and one line in the
  closing section saying a disconnect stops a process and does not forget a machine (FR-012).

- [X] T014 [P] `README.md` and `AGENTS.md` brought level: two scripts, two contracts, the second
  spec, and the one test that needs a keel-cloud.

## Phase 6: The floor

- [X] T015 The whole suite green on `/usr/bin/python3` (3.9.6) and on the newest interpreter
  present (3.12.5) -- 58 tests including the real walk, which ran against the playground
  keel-cloud at `http://localhost:18081` (FR-016).

## What is deliberately not here

- **`keel disconnect` itself.** keel-runtime spec `003-keel-disconnect`, landed at `a05f9bc`. Every
  signal, bound, heartbeat rule and invariant `D1`-`D10` is that spec's; this one calls it.
- **The goodbye to Keel Cloud.** keel-cloud spec `033-agent-session-goodbye` and keel-runtime's
  second pass. Invisible to this contract, in either order.
- **keel-e2e-eval's `make down` and S-001's tail.** Its spec `011-keel-disconnect`, step 6.
- **`keel forget`, `--drain`, `--all-homes`.** Deferred or refused by the design; none of them is
  a thing this skill quietly grows.
