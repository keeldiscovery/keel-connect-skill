# Phase 0 Research: Keel Connect Check

No `[NEEDS CLARIFICATION]` markers were left in the Technical Context. The open questions below are
genuine design decisions this feature's parent task explicitly called out as needing to be written
down rather than decided silently in code.

## 1. Runtime resolution order: `PATH` before `--runtime-path`

**Decision**: try `shutil.which("keel")` first; only fall back to `--runtime-path`/
`KEEL_RUNTIME_PATH` (invoked as `python3 -m keel_runtime <subcommand>`, cwd set to that directory)
if no `keel` command is found.

**Rationale**: `PATH` resolution is the eventual real-world case once keel-cloud spec 020's
`pyproject.toml` packaging ships (`pip install keel-runtime` puts `keel` on `PATH`) -- it should win
whenever it's genuinely available, since it represents the user's actual installed runtime, not a
developer's local checkout. The path/env fallback exists specifically for developing against an
unpublished checkout (e.g. `~/Documents/projects/keel-cloud/keel-runtime`) and must never silently
shadow a real install.

**Alternatives considered**: checking `--runtime-path` first (rejected -- would mean a developer's
leftover `KEEL_RUNTIME_PATH` environment variable could silently override a legitimately installed
runtime, the opposite of the least-surprise behavior wanted); requiring the caller to specify which
mode explicitly every time (rejected -- adds friction to the common case, where a real install just
works with zero flags).

## 2. Detaching the launched `connect` process

**Decision**: `subprocess.Popen(argv, cwd=..., stdout=log_handle, stderr=subprocess.STDOUT,
start_new_session=True)` on POSIX. The parent script does not wait on it, does not keep a pipe open
to it, and closes its own file handle to the log immediately after `Popen` returns (the child has
already duplicated the fd, so it keeps writing fine).

**Rationale**: `start_new_session=True` (a `setsid()` call under the hood) detaches the child from
the parent's process group, so a `SIGINT`/`SIGTERM`/session-end delivered to the script's own process
group -- exactly what happens when a Claude Code tool call is cancelled or its session ends -- does
not propagate to the runtime the script just launched on the user's behalf (FR-004, SC-003). This is
the same posture keel-runtime's own spec 021 `KeelConnectJourneyTest`-style E2E tests use for their
own subprocess management, scaled down to "detach and don't wait" rather than "track and tear down
at test end" since this script's job ends the moment it reports an outcome.

**Alternatives considered**: `nohup`/shell-level backgrounding (rejected -- an extra process layer
and a dependency on a shell being available, when `Popen`'s own `start_new_session` flag does the
same job with no extra process and no shell-quoting risk); waiting on the child with a timeout and
killing it if authorization doesn't complete in time (rejected outright -- approval is a human,
out-of-band action; killing a runtime that's honestly still waiting on a person to click a link would
be actively harmful, not a safety measure).

## 3. Bounded wait duration for the launch signal

**Decision**: default `--wait-seconds` = 8.0, polling the log file every 0.25s.

**Rationale**: spec.md's own instructions describe "a few seconds, not indefinitely" -- long enough
to observe a real device-authorization creation round trip (one HTTP call to Keel Cloud plus process
startup, typically well under a second locally and a few seconds over a real network) with comfortable
margin, short enough that a user asking Claude "keel connect" gets an answer they can act on before
wondering if anything happened at all (SC-001's "roughly ten seconds" ceiling, leaving headroom for
the script's own `status` check and process-spawn overhead ahead of the wait). Overridable via
`--wait-seconds` for a caller with different latency needs (this repository's own tests override it
down to make the timeout-path tests fast, not slow).

**Alternatives considered**: no bound / wait for approval itself (rejected outright by spec.md's
Edge Cases -- approval is an out-of-band human action with no defined upper bound; the script's job
is to report the *code*, not to wait for someone to use it); a much shorter bound like 2s (rejected --
too tight a margin over a real network device-authorization call, would produce false
`authorization_pending_timeout` reports on an honestly-working, just-slightly-slow start).

## 4. Outcome vocabulary: `connected` as a distinct outcome from `already_connected`

**Decision**: two outcomes exist for "the user ends up connected with no code to show them" --
`already_connected` (a runtime was already running *before* this invocation did anything) and
`connected` (this invocation *launched* `connect`, and it connected immediately using a stored
credential, keel-cloud spec 020's restart-reuse behavior, without ever printing a `KEEL_USER_CODE=`
line).

**Rationale**: these are observably different situations a human would phrase differently ("Keel's
already running" vs. "Keel just reconnected using your saved credential") and, more importantly, they
are trivially distinguishable from the log signal already being watched (FR-006) -- collapsing them
into one outcome would either lose that distinction or force `SKILL.md` to re-derive it by comparing
timestamps, which is exactly the kind of duplicated logic this design avoids elsewhere (spec's Scope:
"no duplicated state format"). This also correctly handles a real scenario `keel-cloud`'s own
`KeelConnectJourneyTest` exercises (`aRestartedRuntimeReusesTheStoredCredentialInsteadOfReauthorizing`)
that this script's fresh-launch path would otherwise misreport as a timeout, since no
`KEEL_USER_CODE=` line is ever coming in that case.

**Alternatives considered**: folding `connected` into `authorization_started` with a null
`user_code`/`verification_uri` (rejected -- `contracts/skill-script-output.md`'s own guarantee #1 is
that every key in a shape is always present in that shape; a conditionally-null key breaks that
guarantee for no benefit, since `SKILL.md` needs to phrase these two cases differently anyway).

## 5. Tracking the launched process's pid for a caller that wants to clean it up

**Decision**: every outcome shape that results from actually launching `connect`
(`authorization_started`, `connected`, `authorization_pending_timeout`) includes the launched
process's real `pid` and the `log_file` path it was redirected to, as part of the stable contract
(`contracts/skill-script-output.md` guarantee #4).

**Rationale**: this script has no persistent state of its own and no mechanism to be asked "what did
you launch last time" later -- the only moment it can hand back the pid is the moment it exits. A
caller that legitimately needs to manage the launched process's lifetime (the primary example: the
`keel-cloud` E2E test's `@AfterEach` cleanup, which must not leak a real subprocess across test runs)
can capture it from this JSON directly, with no extra file, database, or IPC channel needed. This
also happens to be generally useful for a human debugging a stuck launch (`log_file`) without adding
any complexity beyond exposing two values the script already computed for its own use.

**Alternatives considered**: writing the pid to a well-known file under `$KEEL_HOME` (rejected --
that's exactly the heartbeat file's job already, owned by `keel-runtime` itself (spec 021), not this
script; duplicating it here would violate the "no duplicated state format" scope statement); requiring
a caller to `pgrep`/parse process lists for the launched `connect` (rejected -- the entire point of
this script's design is that no caller, including this one's own future test suite, should ever need
to).
