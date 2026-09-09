# Feature Specification: There is a door out

**Feature Branch**: `002-keel-disconnect`

**Created**: 2026-09-09

**Status**: Implemented

**Design of record**: keel-cloud `canon/designs/keel-disconnect-design.md` (2026-09-08), with
`canon/designs/keel-skill-design.md` §11. This spec is **step 5** of the disconnect design's §10
implementation order and adds nothing either document does not decide. Every requirement below
cites the invariant id it comes from (the disconnect design's §7, the skill design's §9), and so
does the code.

**Input**: the disconnect design's §2, in its own words: *the skill launches `keel connect`
detached and hands back a pid and a log file. The only way to stop that process is `kill <pid>` in
a terminal -- which is exactly the terminal work the skill exists to spare the founder.*

## Scope, stated first

**What lands here**: `scripts/keel_disconnect.py`; its stable contract at
`contracts/skill-disconnect-output.md`; `SKILL.md`'s second job, its ambiguity rule, its six
disconnect replies and what it says about a "keel connect" straight after a disconnect;
`SKILL.md`'s frontmatter finished to the skill design's decisions 5 and 6; a `disconnect`
subcommand on both fake-runtime fixtures and a third fixture that deliberately has none; and
`tests/test_keel_disconnect.py` -- every outcome through both resolution branches, plus one real
end-to-end walk against a live keel-cloud.

**Not building**: any part of keel-runtime. `keel disconnect` itself, its four outcomes, its
signals, its bounds and its heartbeat handling are keel-runtime's spec `003-keel-disconnect`, which
landed at `a05f9bc`; this repository shells that command and translates its documented output.
Not building the goodbye to Keel Cloud (keel-cloud spec `033-agent-session-goodbye` and
keel-runtime's second pass) -- it is invisible to everything this contract says. Not building
`make dist`, `VERSION` or the packaging trees -- spec `004-skill-packaging`. Not building
`keel forget`, `--drain`, or a `--all-homes` sweep: all three are deferred by the design, and two
of them are refused.

**Depends on** keel-runtime at `a05f9bc` or later, for a `disconnect` subcommand to call. A runtime
older than that is not a failure this skill hides -- it is `internal_error` with a message that
names the cause.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A founder stops the runtime they started (Priority: P1)

A founder said "keel connect" an hour ago. They are done for the day and say "keel disconnect".
The skill runs one script, the runtime stops, and they are told so in a sentence. No terminal, no
pid, no `kill`.

**Why this priority**: this is the whole reason this spec exists. Before it there was a door in and
no door out.

**Independent Test**: with a real runtime connected on a scratch home, run the script; assert
`disconnected`, that the pid it names is not alive, and that the heartbeat is gone.

**Acceptance Scenarios**:

1. **Given** a runtime running and connected on this home, **When** the script runs, **Then** it
   reports `disconnected` with the pid, how long it waited and which signal did it -- **after** the
   process was observed gone, never before.
2. **Given** the same, **When** the script runs a second time, **Then** it reports `not_running`
   and does nothing.
3. **Given** either run, **Then** the home's `credentials.json` is untouched, so a later "keel
   connect" needs no device code and no browser.

### User Story 2 - A founder stops something that is not running (Priority: P1)

A founder says "keel disconnect" when nothing is running -- they forgot, or they never started one,
or it died overnight. Nothing bad happens, and they are told the truth.

**Why this priority**: an ambiguous request resolves toward disconnect precisely because this case
is harmless (S1). If it were not, the whole ambiguity rule would be wrong.

**Independent Test**: run the script against an empty home; assert `not_running` and exit 0.

**Acceptance Scenarios**:

1. **Given** a home with no heartbeat, **When** the script runs, **Then** `not_running`, exit 0,
   and no process was signalled.
2. **Given** a home whose heartbeat is malformed, unreadable, or short a required field, **When**
   the script runs, **Then** the same one answer -- `not_running` (D1).
3. **Given** a heartbeat naming a pid that is not alive -- the trace of a runtime that crashed --
   **When** the script runs, **Then** `stale_pid_cleared`, the file is gone, and **nothing was
   signalled** (D2).

### User Story 3 - A runtime that will not stop (Priority: P2)

The runtime is inside a call the operating system will not interrupt. `SIGTERM` and `SIGKILL` both
go unanswered inside the 15-second bound. The founder is told honestly, rather than waiting.

**Why this priority**: the honest failure is the only one that keeps two runtimes off one home.

**Independent Test**: a fake runtime reporting `timeout`; assert `did_not_stop`, the pid, and a
message that names the cause.

**Acceptance Scenarios**:

1. **Given** a runtime that survives both signals, **When** the script runs, **Then**
   `did_not_stop` with the pid, `waited_ms` and a plain-language `message`.
2. **Given** that outcome, **Then** `SKILL.md` tells the agent **not** to offer a "keel connect"
   (S2): the old runtime is still polling, and a second one against the same home is worse than
   the problem.

### User Story 4 - A runtime too old to have the command (Priority: P2)

Someone has a `keel` on `PATH` from before `disconnect` existed. The skill says so, and says what
to do about it.

**Why this priority**: "update your keel-runtime" is a remedy; "something went wrong" is not.

**Independent Test**: a fixture with no `disconnect` subparser at all, so the failure is a real
`argparse` exit 2 with usage on stderr rather than a mock of one.

**Acceptance Scenarios**:

1. **Given** a runtime with no `disconnect` subcommand, **When** the script runs, **Then**
   `internal_error`, exit 1, and a `message` naming the missing subcommand and the update.
2. **Given** a runtime whose `disconnect` prints something other than one JSON line, or an outcome
   this skill does not know, **Then** `internal_error` as well, each with its own sentence.

### User Story 5 - The agent picks the right door (Priority: P1)

A user says something that could mean either job. The agent asks, rather than guessing -- and if it
must lean, it leans toward disconnect.

**Why this priority**: the connect check is the only one of the two scripts that can do something
on a misread the founder then has to undo.

**Independent Test**: `SKILL.md` carries the rule in words, before either script's section.

**Acceptance Scenarios**:

1. **Given** an ambiguous request, **When** the agent reads `SKILL.md`, **Then** it is told to ask,
   and told explicitly never to run the connect check to find out (S1).

### Edge Cases

- **A runtime the skill did not start.** No special case, by design. The heartbeat -- not the
  launcher -- is what "the runtime on this home" means, and a `keel connect` typed in a terminal
  writes the same one.
- **Two homes.** `KEEL_HOME` partitions everything, and this script resolves a home exactly as its
  sibling does, so a disconnect in a playground can never reach a real runtime. "Disconnect
  everything" is not a thing this script does: it knows one home.
- **Pid reuse.** Accepted and unmitigated at the runtime's level (design decision 11), and this
  script adds no exposure: it never supplies a pid, and there is deliberately no `--pid` flag.
- **A "keel connect" seconds after a disconnect.** Safe after `disconnected` (the pid was observed
  gone); refused after `did_not_stop`; and during the 15 seconds, a genuine and named window that
  resolves itself. `SKILL.md` says all three in the founder's words.
- **A job in flight.** Abandoned -- not completed, not failed. That is what Ctrl+C already does,
  and this skill neither changes it nor speaks for the job.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** The skill MUST carry a second script, `scripts/keel_disconnect.py`, beside the first
  -- not a `--disconnect` mode of it. The connect contract is titled for one script and two other
  repositories read it (design §5.1).
- **FR-002** The script MUST resolve the runtime through `scripts/_runtime_location.py`, imported
  and used **whole**: one resolution order in this skill, written down in one place (skill design
  §11, §3.2).
- **FR-003** The script MUST invoke the resolved runtime's `disconnect`, passing `--home` when and
  only when this script was given one, resolved by the same rule `keel_connect_check.py` uses.
- **FR-004** The script MUST print **exactly one line** of JSON on stdout and nothing else, and
  MUST exit 0 for every outcome except `internal_error`, which exits 1.
- **FR-005** `outcome` MUST be one of exactly six values: `disconnected`, `not_running`,
  `stale_pid_cleared`, `did_not_stop`, `runtime_unavailable`, `internal_error`.
- **FR-006** Every shape MUST carry `environment` -- which Keel this is, relayed from the runtime,
  `null` when none answered. The script MUST NOT carry a base URL or an environment table of its
  own (X-5).
- **FR-007** The runtime's `home` and `base_url` keys MUST NOT be carried up. `environment` is the
  one key for which Keel, never two.
- **FR-008** The script MUST NOT be capable of starting a `keel connect`, under any outcome (S3).
- **FR-009** The script MUST NOT make a network call and MUST NOT touch a credential.
- **FR-010** A runtime that breaks its own contract -- crash, non-zero exit, not one JSON line, no
  `outcome`, an unknown `outcome` -- MUST become `internal_error` with a message that names what
  happened; the missing-subcommand case MUST name the update as its remedy.
- **FR-011** The contract MUST live at `specs/002-keel-disconnect/contracts/skill-disconnect-output.md`
  in the same five-part shape as its sibling, and a change to it is a major version bump of the
  skill.
- **FR-012** `SKILL.md` MUST gain the second job, its trigger phrasings, the ambiguity rule (S1),
  a reply for each of the six outcomes, and what "keel connect" says if a disconnect is mid-way.
- **FR-013** `SKILL.md`'s frontmatter MUST carry exactly `name`, `description` and `license`
  (skill design decision 6), with a trigger-first `description` naming **both** jobs' phrasings
  (decision 5), under 500 characters, in a frontmatter under 1,024.
- **FR-014** No founder-facing message may name `--runtime-path` or `KEEL_RUNTIME_PATH` (X-4), and
  no reply may name an agent host (D5).
- **FR-015** Tests MUST cover every one of the six outcomes through **both** resolution branches
  against fake runtimes, and MUST include one real end-to-end walk -- a real `connect` against a
  live keel-cloud, then `disconnected`, then `not_running` -- which skips itself when no keel-cloud
  is listening, so the suite stays offline by default.
- **FR-016** The whole suite MUST be green on Python 3.9 and on the newest interpreter present.

### Non-functional / invariants carried

`S1`, `S2`, `S3` from the disconnect design §7; `X-1`, `X-2`, `X-4`, `X-5`, `D5` from the skill
design §9. `D1`-`D10` belong to keel-runtime and are **not** re-implemented here -- they are
depended on, through the contract.

## Key Entities

- **The disconnect script** -- one file, stdlib only, invoked as a subprocess, printing one line.
- **The contract** -- six shapes, eight guarantees, the one thing other repositories may depend on.
- **The runtime's own contract** -- four shapes; this script's input, not its output.
- **The fake runtimes** -- three fixtures now: two that have `disconnect`, and one that does not.

## Success Criteria *(mandatory)*

- **SC-001** A founder who says "keel disconnect" gets a sentence, not a pid to kill.
- **SC-002** Saying it twice is safe, and the second answer is `not_running`.
- **SC-003** A `disconnected` is never reported for a process still alive.
- **SC-004** A `did_not_stop` never leads to an offer of a connect.
- **SC-005** Nothing this script does can start a process, and a test proves it by the absence of
  the fixtures' own launch marker.
- **SC-006** The credential survives every outcome.
- **SC-007** The whole suite runs offline, and the one test that does not says so in its name and
  skips itself.

## Assumptions

- keel-runtime at `a05f9bc` or later is what this skill carries; `RUNTIME_VERSION` records it.
- keel-e2e-eval's `make down` and S-001 tail (its spec `011-keel-disconnect`) are step 6 and are
  not this repository's to write.
- The goodbye to Keel Cloud may land before or after this spec without changing a word of the
  contract.
