# Feature Specification: The runtime travels inside the skill

**Feature Branch**: `003-bundled-runtime`

**Created**: 2026-09-08

**Status**: Implemented

**Design of record**: keel-cloud `canon/designs/keel-skill-design.md` (2026-09-08). This spec is
**step 3** of its §13 implementation order and adds nothing that document does not decide. Every
requirement below cites the invariant id it comes from (§9), and so does the code.

**Input**: The design's §2, in its own words: *a founder says "keel connect" and the skill answers
`runtime_unavailable` with a remedy they must perform in a terminal, against a package that is not
published. Remove the step -- without asking anyone to run a binary they have never heard of.*

## Scope, stated first

**What lands here**: `make runtime`; the resolution order with the bundled runtime beating a `keel`
on `PATH`; the Python 3.9 version gate; `--host` and its detection table; `environment` on every
outcome; the output contract rewritten for seven shapes; `SKILL.md`'s seven replies, its Python
clause and its one host line; the shared `scripts/_runtime_location.py`; and this repository's own
3.9-3.13 matrix.

**Not building**: `make dist`, `VERSION`, `packaging/`, the four packaging trees and the L1
packaging tests -- those are spec `004-skill-packaging`. Not building `scripts/keel_disconnect.py`
either (spec `002-keel-disconnect`), though `_runtime_location.py` is written to be used by it
whole. Not building any part of keel-runtime: this repository copies that package and calls it, and
never edits it.

**Depends on** keel-runtime's spec `004-shipped-runtime` for a runtime to name -- `requires-python
>= 3.9`, the derived home, `--version`, and `home`/`environment`/`base_url` on `status`. That
landed at `8dacbbf`; this skill carries it and records which one in `RUNTIME_VERSION`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A founder who has never had Keel says it once (Priority: P1)

A founder in an agent session types "keel connect". They have never installed anything called Keel.
The skill runs its script, which finds the runtime sitting inside itself, sees nothing running,
starts it, and comes back with a device code and an approval URL -- on the **first** invocation, on
a fresh machine, with no terminal step in between.

**Why this priority**: this is the whole reason this spec exists. Before it, this founder got
`runtime_unavailable` and homework against a package that returns 404 on PyPI.

**Independent Test**: from a relocated copy of the skill with `keel_runtime/` beside `scripts/` and
no `keel` anywhere on `PATH`, run the script with no flags; assert an outcome that required the
runtime to have run, and that the copy beside the script is what ran.

**Acceptance Scenarios**:

1. **Given** a skill directory carrying `keel_runtime/` and no `keel` on `PATH`, **When** the
   script runs with no flags, **Then** it resolves the bundled package, runs `status` through it,
   and reaches `authorization_started`, `connected` or `already_connected` -- never
   `runtime_unavailable`.
2. **Given** the same directory **and** a `keel` on `PATH` that would answer differently, **When**
   the script runs, **Then** the **bundled** runtime answers and the one on `PATH` is not run.
3. **Given** a skill directory with no `keel_runtime/` and no `keel` on `PATH`, **When** the script
   runs, **Then** it reports `runtime_unavailable` with a message that names neither a package
   index nor the development override.

### User Story 2 - A founder on an old Python gets a sentence (Priority: P1)

A founder whose `python3` is 3.8 says "keel connect". The script must not raise a `SyntaxError`,
must not raise a traceback, and must not be silent: it prints one line of JSON naming the version
they have, the version Keel needs, and the one command that installs it on their operating system.

**Why this priority**: co-equal with Story 1. Python is now the single prerequisite, so the failure
to have it is the single remaining wall, and a wall a founder can read their way past is not one.

**Independent Test**: execute the real script file under a runner that has overwritten
`sys.version_info` (and `sys.platform`, for the per-OS clauses); assert one JSON line,
`python_too_old`, exit 0, empty stderr, and the install command for that platform in the `message`.

**Acceptance Scenarios**:

1. **Given** an interpreter below 3.9, **When** the script runs, **Then** it prints exactly one
   line of JSON with `outcome: "python_too_old"`, `found`, `required: "3.9"`, `environment: null`
   and a `message`, and exits 0.
2. **Given** the same, **and** a perfectly good runtime available to it, **When** the script runs,
   **Then** it still reports `python_too_old` -- nothing is resolved and nothing is run before the
   gate.
3. **Given** 3.9 exactly, **When** the script runs, **Then** the gate does not fire.

### User Story 3 - A developer debugging the runtime (Priority: P2)

A developer, or keel-e2e-eval, points `KEEL_RUNTIME_PATH` at a keel-runtime checkout. That checkout
must win outright, so nobody debugging the runtime is silently testing a release instead.

**Why this priority**: lower than the two founder stories, but it is the only way anyone works on
the runtime at all, and getting the order wrong makes a whole class of debugging session lie.

**Independent Test**: a relocated skill with a *real* `keel_runtime/` bundled and a *fake* checkout
named by the flag; assert the fake answered.

**Acceptance Scenarios**:

1. **Given** both a checkout and a bundled runtime, **When** the script runs, **Then** the checkout
   answers.
2. **Given** a `--runtime-path` that holds no `keel_runtime/__main__.py`, **When** the script runs,
   **Then** it is ignored and the next rule runs -- not an error.
3. **Given** any outcome at all, **When** the reply is read, **Then** no founder-facing message
   names `--runtime-path` or `KEEL_RUNTIME_PATH` (X-4).

### User Story 4 - Two hosts, one skill (Priority: P2)

The same skill directory is read by two different agent hosts. Each should end up running the
executor that matches it, without the skill growing a second copy, a second outcome, or a host name
in anything a user reads.

**Why this priority**: the founder's words are *we need to support both*. It is one flag and one
table here, and everything expensive about it lives in keel-runtime's spec `005-copilot-executor`.

**Independent Test**: the detection table as a pure function over a dict, plus one end-to-end run
asserting the chosen executor reached `connect`'s argv and no outcome shape changed.

**Acceptance Scenarios**:

1. **Given** an environment naming exactly one host, **When** a `connect` is launched, **Then**
   `--executor <that host's executor>` is passed to it.
2. **Given** an environment naming two different hosts at once, **When** a `connect` is launched,
   **Then** no `--executor` is passed at all -- two answers mean no answer.
3. **Given** an explicit `--executor`, **When** anything is launched, **Then** that value is used
   and the table is not consulted.
4. **Given** any of the above, **When** the outcome is read, **Then** its key set is unchanged --
   which executor was chosen is never a JSON key.

### User Story 5 - Which Keel is this? (Priority: P2)

A founder with a playground Keel and a real one must never have to infer which they just talked to,
and must never present one's credential to the other.

**Independent Test**: assert `environment` present on every shape; assert it is `null` exactly when
no runtime answered; assert the script passes `--home` only when it was given one, and puts the
launch log in the home `status` named.

**Acceptance Scenarios**:

1. **Given** any outcome, **When** it is read, **Then** `environment` is a key on it.
2. **Given** a runtime that reports no `environment`, **When** the outcome is read, **Then**
   `environment` is `null` -- the skill guesses nothing.
3. **Given** no `--home` and no `KEEL_HOME`, **When** a `connect` is launched, **Then** no `--home`
   is passed to it and the launch log is written to the home `status` reported.

### Edge Cases

- A `--runtime-path` that exists but holds no `keel_runtime/__main__.py`: not a runtime, so the
  order continues rather than failing.
- A working directory that itself holds an unrelated `keel_runtime/`: `python3 -m` puts the working
  directory ahead of `PYTHONPATH` on the 3.9 floor, so the resolved runtime would be silently
  shadowed. `PYTHONSAFEPATH=1` fixes this exactly and is 3.11+; the module branch therefore also
  runs with `cwd` set to the directory it resolved. This is the **one documented deviation** from
  the design's §3.2 (which says `cwd` is left alone), and it is written down in
  `scripts/_runtime_location.py`'s own docstring beside the measurement that forced it.
- `status` unreachable, crashing, or answering something that is not its own contract: a genuine
  internal problem, reported as `internal_error`, the one outcome that exits non-zero.
- A runtime older than keel-runtime's spec `004`, reporting no `home` and no `environment`: the
  skill reports `environment: null` and falls back to `~/.keel` for the log. It does not invent an
  address.
- No `python3` on the machine at all: not an outcome and cannot be. The answer lives in `SKILL.md`
  and `README.md`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `make runtime` MUST copy `keel_runtime/` from a keel-runtime checkout into this
  repository's root, and MUST refuse when that checkout is not a git checkout, is not on a commit,
  or is dirty -- `RUNTIME_VERSION` has to be able to name exactly what was copied (D2).
- **FR-002**: `make runtime` MUST write `RUNTIME_VERSION` naming the runtime it copied: the exact
  tag when the checkout is on one, and `<__version__>+<short sha>` otherwise, since keel-runtime
  has no tags yet.
- **FR-003**: `keel_runtime/` MUST be gitignored in this repository and `RUNTIME_VERSION` MUST NOT
  be. One copy of the runtime's source exists in the world and it is in keel-runtime (D2); the
  ignore MUST be rooted so the fake runtime fixtures under `tests/` are untouched.
- **FR-004**: The script MUST resolve the runtime in this order (§3.2): a checkout named by
  `--runtime-path`/`KEEL_RUNTIME_PATH`; the `keel_runtime/` beside the skill; a `keel` on `PATH`.
  Neither of the first two counts unless it holds `keel_runtime/__main__.py`. Nothing resolving
  MUST produce `runtime_unavailable`, never an exception.
- **FR-005**: Both package branches MUST be invoked as `<sys.executable> -m keel_runtime` with the
  resolved directory prepended to the child's `PYTHONPATH` (§3.2), and `sys.executable` -- the
  interpreter that ran the script, already guaranteed >= 3.9 by FR-006 -- MUST be what runs it.
- **FR-006**: The version gate MUST be the first executable statement in
  `scripts/keel_connect_check.py`, above every import but `sys`, in syntax every Python 3 parses
  (X-3). Below 3.9 it MUST print one line of JSON (`python_too_old`) naming the version found, the
  version required and one install command for the running operating system, and exit 0 -- having
  resolved nothing and run nothing.
- **FR-007**: The script MUST accept `--host {claude,copilot,auto}`, default `auto`, and MUST run
  the design's §5.3 step-2 detection table over `COPILOT_AGENT_SESSION_ID`, `COPILOT_CLI`,
  `CLAUDECODE` and `AI_AGENT`. Exactly one answer is taken; two different answers are taken as no
  answer.
- **FR-008**: The detected host MUST reach the launched `connect` as `--executor <name>`, and
  **only** there: never on a `status` call, never when `--executor` was given (which wins
  outright), and never when the table is silent or ambiguous. **No outcome shape may change because
  of it** (decision 15).
- **FR-009**: `environment` MUST be a key on all seven outcome shapes, carrying the value the
  runtime's `status` reported, and MUST be `null` exactly when no runtime answered --
  `python_too_old`, `runtime_unavailable`, and an `internal_error` raised before `status` returned.
  The skill MUST NOT hard-code a base URL, an environment table, or any part of a
  `verification_uri` (X-5).
- **FR-010**: `already_connected` MUST lose `base_url` and gain `environment` -- one key for which
  Keel, never two (§7). This is a breaking change to that shape and is recorded as such.
- **FR-011**: `--home`/`KEEL_HOME` MUST be passed to `status` and `connect` only when one was
  given; otherwise the runtime derives its own home and the script relays the `home` that `status`
  reported, and writes the launch log there (§6.3).
- **FR-012**: This repository MUST run its own tests on Python 3.9-3.13, staging the runtime the
  way `make runtime` does rather than by hand (T-1), installing neither `keyring` nor `jsonschema`
  (R-2).
- **FR-013**: `scripts/_runtime_location.py` MUST hold the resolution order once, for both this
  script and (spec `002-keel-disconnect`) `keel_disconnect.py`, which will use it whole.
- **FR-014**: `SKILL.md` MUST carry a reply for each of the seven outcomes, the clause naming the
  per-OS Python install for a user who has no `python3` at all, and exactly one line naming an
  agent host -- marked with a comment saying it is the deliberate D5 exception.
- **FR-015**: The `runtime_unavailable` message MUST NOT name a package index, `--runtime-path` or
  `KEEL_RUNTIME_PATH` (X-4). Nothing is installed any more, so a skill with no runtime beside it is
  a skill that was copied wrong.
- **FR-016**: `specs/001-keel-connect-check/contracts/skill-script-output.md` MUST be rewritten in
  place for seven shapes. Its location does not move: it is one contract, and the design names that
  path.
- **FR-017**: The script MUST require no dependency beyond the Python standard library.

### Non-functional / invariants carried

X-1 (one line of JSON, exit 1 only for `internal_error`), X-2 (no key outside a shape without the
contract changing first), X-3, X-4, X-5, X-6 (nothing written outside the runtime's home; no `PATH`
or shell-profile edit, ever), D2, D4 (no ecosystem name in `SKILL.md` or the scripts), D5, R-2,
T-1.

## Key Entities

- **Outcome** -- the single JSON object the script prints. Seven shapes, exhaustively documented by
  `specs/001-keel-connect-check/contracts/skill-script-output.md`, which is this repository's one
  external interface (D3).
- **RuntimeLocation** -- a resolved runtime: an argv prefix, an optional directory that must reach
  the child's `PYTHONPATH`, and which of the three rules found it (`checkout`, `bundled`, `path`).
  The `source` is deliberately **not** an outcome key; it exists so a developer and a test can see
  *why*, not only *what*.
- **RUNTIME_VERSION** -- one line naming which keel-runtime this skill carries. The only committed
  trace of a package that is not.

## Success Criteria *(mandatory)*

- **SC-001**: A founder with no Keel installation and no configuration says "keel connect" once and
  receives a code and a URL, or a clear reason why not -- with no terminal step in between.
- **SC-002**: A founder on Python 3.8 receives one sentence naming their version, the version
  needed and the command that installs it, and no traceback.
- **SC-003**: The runtime that runs is the one that travelled: with a `keel` on `PATH` answering
  differently, the bundled copy's answer is what comes back.
- **SC-004**: Every one of the seven outcomes is produced by a fast, offline test in this
  repository, and the whole suite is green on the 3.9 floor and on the newest interpreter present.
- **SC-005**: No reply, message or outcome shape names an agent host, an ecosystem, a base URL, or
  the development override.

## Assumptions

- keel-runtime at the commit `RUNTIME_VERSION` names is 3.9-clean and reports `home`, `base_url`
  and `environment` from `status` in both shapes. Measured, not assumed: its own matrix runs
  3.9-3.13 and this repository's tests run its `status` and `--version` directly.
- `CLOUD_BASE_URL` is still the empty placeholder in keel-runtime, so `environment` is `null` for a
  founder who has set nothing at all. That is the design's step 8, blocked on an AWS deployment
  design, and nothing here changes when it lands.
- The runtime does not yet accept `--executor copilot`: that name arrives with keel-runtime's spec
  `005-copilot-executor`. Until it does, a Copilot host that reaches the detection table will hand
  the runtime a name it rejects. `claude` is unaffected -- the script sends `claude-code`, the
  permanent accepted alias (C-12), which today's runtime knows.
- Windows detached-launch behaviour is the `CREATE_NEW_PROCESS_GROUP` path and is exercised by the
  matrix, not by a bed on the founder's machine.
