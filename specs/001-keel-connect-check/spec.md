# Feature Specification: Keel Connect Check (skill)

**Feature Branch**: `001-keel-connect-check`

**Created**: 2026-09-02

**Status**: Draft

**Input**: User description: "A Claude Code skill that, when a user says or clearly means 'keel
connect', checks whether a local `keel-runtime` process (keel-cloud spec 020) is already running
and connected to Keel Cloud, and if not, launches `keel connect` for them in the background and
relays the device-authorization code/URL they need to approve. It has no knowledge of Keel's
discovery protocol, MCP, or the unrelated `keel-discovery` MCP skill in the sibling `keel-skill`
repository -- it only needs to understand the keel runtime. It relies entirely on `keel-runtime
status` (keel-cloud spec 021) for its liveness answer -- no process-list parsing, no duplicated
state format."

## Scope, stated first

**This skill's whole job**: decide, cheaply, whether to launch `keel connect` on the user's behalf,
and if it does launch it, hand back exactly what a human needs to approve the device. It does not
run inference jobs, does not know what Keel Cloud does with a connected runtime once it exists, and
does not need any code shared with `keel-discovery` (the MCP-hosted, zero-shell-access discovery
skill in the separate `keel-skill` repository) beyond both being "a Keel-branded Claude Code
artifact" -- there is no protocol, format, or dependency relationship between the two.

**Two deliverables**: a deterministic helper script (`scripts/keel_connect_check.py`) that does all
the actual work and prints one line of stable JSON, and `SKILL.md`, which tells Claude when to run
the script and how to turn its JSON into a sentence a human can act on. All of the real design
decisions live in the script's behavior (below) -- `SKILL.md` itself is a thin instruction layer
over a contract the script already guarantees.

**Not building**: the keel-runtime package itself (keel-cloud spec 020), its `status` subcommand
(keel-cloud spec 021), or the Keel Cloud server. This skill is a caller of all three, never a
reimplementation of any of them. The proof that the caller and the real three form a working chain
is a separate, cross-repo Java test living in `keel-cloud` (out of scope for this repository's own
test suite, which proves the script's logic against a fake runtime it fully controls).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A user asks Claude to connect Keel, and nothing is running yet (Priority: P1)

A founder, in a Claude Code session, types "keel connect" (or "start the keel runtime", "connect me
to keel", or similar). No `keel-runtime` process is currently running on their machine. Claude runs
the skill's script, which finds no runtime connected, launches `keel connect` in the background, and
reports back the device code and approval URL within a few seconds. Claude relays both to the user
in plain language and tells them they can say "keel connect" again afterward to confirm the
connection went through.

**Why this priority**: this is the only scenario that requires the skill to *do* anything beyond
report a fact -- every other scenario is a variant of "check and report."

**Independent Test**: run the script against a fake runtime configured to behave exactly like a
fresh `keel connect` invocation (prints `KEEL_USER_CODE=`/`KEEL_VERIFICATION_URI=`, then blocks);
assert the script's JSON reports `authorization_started` with the matching code and URL, and that
the launched process is still running (detached, not blocked on the script's own exit).

**Acceptance Scenarios**:

1. **Given** no runtime is running, **When** the script runs, **Then** it first checks
   `keel-runtime status`, sees `running: false`, launches `keel connect` detached (it outlives the
   script's own process), and within a bounded wait reports `{"outcome": "authorization_started",
   "user_code": "...", "verification_uri": "...", ...}`.
2. **Given** the same situation, but the launched `keel connect` process has a stored credential
   from a previous session (keel-cloud spec 020's restart-reuse behavior) and therefore skips device
   authorization entirely, **When** the script runs, **Then** it reports `{"outcome": "connected",
   "agent_session_id": "...", ...}` instead -- no code or URL exists to relay because none was
   needed.
3. **Given** the same starting situation, but the launched process prints neither signal within the
   bounded wait (a slow start, a hung network call before the first log line), **When** the wait
   expires, **Then** the script reports `{"outcome": "authorization_pending_timeout", ...}` rather
   than waiting indefinitely -- approval is a human, out-of-band step no script can block on, and a
   slow *start* is a different problem the caller should be told about, not silently absorbed into a
   longer and longer wait.

### User Story 2 - A user asks to connect, and a runtime is already connected (Priority: P1)

The same user, moments later (or on a machine where a runtime has been running for a while), says
"keel connect" again. A `keel-runtime` process is already running and connected. The script reports
this immediately, without launching a second, redundant process.

**Why this priority**: co-equal with Story 1 -- avoiding a redundant launch is the other half of
this skill's entire reason to exist (spec 021's own stated purpose for `status`).

**Independent Test**: point the script at a fake runtime whose `status` always reports
`running: true`; assert the script's JSON is `{"outcome": "already_connected", ...}` and that no
`connect` subprocess was launched (the fake runtime records whether its `connect` subcommand was
ever invoked).

**Acceptance Scenarios**:

1. **Given** `keel-runtime status` reports `running: true`, **When** the script runs, **Then** it
   reports `{"outcome": "already_connected", "agent_session_id": "...", ...}` and performs no
   `connect` launch at all.

### User Story 3 - No usable runtime installation can be found (Priority: P2)

A user says "keel connect" on a machine where `keel-runtime` was never installed and no dev-mode
checkout is configured. The script cannot find a `keel` command on `PATH`, and no
`--runtime-path`/`KEEL_RUNTIME_PATH` points at a usable checkout either.

**Why this priority**: lower than Stories 1-2 because it's the "nothing to check" case, but still a
first-class, must-not-crash outcome -- a user without the runtime installed is exactly the person
who most needs a clear next step, not a traceback.

**Independent Test**: run the script with `PATH` scrubbed of any `keel` executable and no
`--runtime-path`/`KEEL_RUNTIME_PATH` set (or pointed at a directory with no `keel_runtime` package
in it); assert `{"outcome": "runtime_unavailable", "message": "..."}` and exit code 0.

**Acceptance Scenarios**:

1. **Given** neither resolution path finds a runtime, **When** the script runs, **Then** it reports
   `{"outcome": "runtime_unavailable", "message": "<a clear, actionable explanation>"}` and exits 0
   -- this is a normal, informational answer, not a crash.

### Edge Cases

- Both a `keel` command on `PATH` and a `--runtime-path`/`KEEL_RUNTIME_PATH` are available: `PATH`
  wins (FR-002) -- it represents the eventual real-world, packaged case (keel-cloud spec 020's
  `pyproject.toml` `[project.scripts]` entry) once `keel-runtime` ships that way; the path override
  exists for development against an unpublished checkout, and should not silently shadow a real
  install.
- `keel-runtime status` itself is unreachable, crashes, or returns output that doesn't match its own
  stable contract (keel-cloud spec 021's `status-cli-output.md`) -- this is a genuine internal
  problem (either this script's invocation of it is wrong, or the located runtime is broken in a way
  spec 021 doesn't anticipate), not an ordinary "not connected" answer. The script reports it
  distinctly (`internal_error`) and is the one case that exits non-zero.
- The bounded wait for the launch signal is inherently a race against a real device-authorization
  HTTP round trip plus process startup; it is deliberately generous but finite (a few seconds, not
  indefinite) -- `authorization_pending_timeout` exists specifically so a slow start is reported
  honestly rather than the script hanging or guessing.
- The script must never leave a launched `keel connect` process attached to its own lifetime -- a
  Claude Code tool invocation that times out or whose parent session ends must not kill the runtime
  it just started on the user's behalf.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The script MUST determine, before doing anything else, whether a `keel-runtime` is
  already running and connected, by invoking `keel-runtime status` (never by parsing process lists,
  reading any file the runtime owns directly, or otherwise duplicating spec 021's own liveness
  logic) and parsing its documented JSON contract.
- **FR-002**: The script MUST resolve which runtime installation to invoke in this order: (a) a
  `keel` executable found on `PATH`; (b) a directory supplied via `--runtime-path` or the
  `KEEL_RUNTIME_PATH` environment variable, invoked as `python3 -m keel_runtime <subcommand>` with
  that directory as the subprocess's working directory; (c) neither resolves -> report
  `runtime_unavailable`, never raise an unhandled exception.
- **FR-003**: If `status` reports `running: true`, the script MUST report `already_connected` (with
  the connected `agent_session_id`) and MUST NOT launch a `connect` process.
- **FR-004**: If `status` reports `running: false` (with or without `stale_pid` -- both are "not
  running" from this script's point of view; a stale zombie process is not this script's job to
  clean up), the script MUST launch `keel connect` **detached** -- it must still be running after
  this script's own process exits, achieved via a new process group/session on POSIX
  (`start_new_session=True`) so a Claude Code tool-call timeout or session end cannot take the
  runtime down with it.
- **FR-005**: The launched `connect` process's combined stdout/stderr MUST be redirected to a log
  file under the resolved `$KEEL_HOME` (flag > `KEEL_HOME` env > `~/.keel`, the same precedence
  keel-runtime itself uses), so its human-facing startup lines remain inspectable after the script
  exits.
- **FR-006**: After launching `connect`, the script MUST watch that log file for a bounded time (not
  indefinitely) for one of two signals keel-runtime's existing `cli.py`/`auth.py` already print:
  `KEEL_USER_CODE=`/`KEEL_VERIFICATION_URI=` together (device authorization needed) or
  `KEEL_AGENT_SESSION_ID=` alone (a stored credential was reused; already connected, no human step
  needed). Whichever appears first within the wait decides the outcome; neither appearing before the
  wait elapses is its own outcome (`authorization_pending_timeout`), not an error.
- **FR-007**: The script MUST print its own stable JSON output contract -- documented in
  `contracts/skill-script-output.md` -- as exactly one line to stdout, and nothing else on stdout.
  This is the interface `SKILL.md` (and no other code, in this repository or `keel-cloud`) is
  allowed to depend on.
- **FR-008**: The script MUST exit 0 for every outcome in FR-002 through FR-006 above -- "not
  connected," "runtime not installed," and "no signal yet" are all normal, informational answers.
  The script MUST exit non-zero only for a genuine internal failure (the located runtime's `status`
  subprocess crashes, produces unparseable output, or otherwise breaks its own documented contract;
  or the `connect` subprocess fails to even start) -- reported as `internal_error`, never a bare
  traceback.
- **FR-009**: The script MUST require no dependency beyond the Python standard library, matching
  `keel-runtime`'s own posture (keel-cloud spec 020 FR-025) -- it is invoked as a subprocess by
  Claude Code and must run on a bare `python3`.
- **FR-010**: `SKILL.md` MUST state its trigger condition in its `description` frontmatter clearly
  enough that Claude Code invokes it whenever a user types or clearly means "keel connect" (connect,
  start, launch, or check the local Keel runtime), and MUST instruct Claude how to turn each of the
  script's documented outcomes into a plain-language reply, including relaying the device code/URL
  verbatim and reminding the user they can ask again later to confirm.

## Key Entities

- **Outcome**: the single JSON object the script prints -- not a database row, not persisted
  anywhere; one point-in-time answer per invocation. Its exhaustive shapes are
  `contracts/skill-script-output.md`, this repository's own stable external contract (the same role
  keel-cloud spec 021's `status-cli-output.md` plays for `keel-runtime status`, which this script in
  turn depends on).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user who says "keel connect" with nothing running receives, within roughly ten
  seconds, either an approval code and URL or a clear reason why not -- never a hang, a crash, or
  silence.
- **SC-002**: A user who says "keel connect" while already connected never has a second, redundant
  `keel connect` process launched on their behalf.
- **SC-003**: A launched `keel connect` process survives the script's own exit and the surrounding
  Claude Code tool call completing -- proven by the cross-repo `keel-cloud` E2E test (spec 020/021's
  real runtime and Cloud, see that repository's `KeelConnectSkillJourneyTest`), where the process
  the script launches goes on to complete a real device-authorization approval and connect, entirely
  after the script that launched it has already exited.
- **SC-004**: Every outcome this script can produce is covered by a fast, offline unit test in this
  repository, run against a fake runtime this repository fully controls -- no test in this
  repository depends on a real `keel-runtime` install or a real Keel Cloud server.

## Assumptions

- Single-machine, single-user scope, matching keel-cloud spec 020/021 -- this skill checks and
  starts a runtime on the same machine Claude Code itself is running on.
- The bounded wait's exact duration is an implementation decision (plan.md), not fixed here, beyond
  the constraint in FR-006 that it must be finite and "a few seconds," not indefinite -- long enough
  to observe a normal local device-authorization round trip, short enough that a genuinely slow
  start is reported rather than silently absorbed.
- `keel-runtime status`'s own contract (keel-cloud spec 021) is trusted as-is; this script does not
  re-derive or second-guess its liveness determination, only parses and relays it.
- The real, three-tier proof (this script -> a real `keel-runtime` -> a real Keel Cloud) is a
  separate cross-repo E2E test living in `keel-cloud`, not this repository -- explicitly out of
  scope for this repository's own test suite (which proves the script's own logic in isolation).
