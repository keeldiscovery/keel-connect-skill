# Contract: `keel_connect_check.py` CLI output

**This is the stable, external contract** (spec FR-007) -- the one thing `SKILL.md` (and anything
else that shells out to this script, including the cross-repo E2E test in `keel-cloud`) is allowed
to depend on. Everything else about this script's implementation (the log file's name, the exact
poll interval, internal helper function names) may change; this contract may not, without this file
changing first.

This script is itself a caller of `keel-runtime status`'s own stable contract (keel-cloud
`specs/021-keel-runtime-status/contracts/status-cli-output.md`) -- this file documents a distinct,
one-level-higher contract, not a restatement of that one.

## Invocation

```text
python3 scripts/keel_connect_check.py [--runtime-path PATH] [--base-url URL] [--executor NAME]
    [--credential-backend {auto,file,keyring}] [--no-browser] [--home PATH]
    [--wait-seconds SECONDS]
```

- `--runtime-path` / `KEEL_RUNTIME_PATH` (env, flag wins): a dev-mode checkout directory containing
  a `keel_runtime/` package (e.g. a `keel-cloud` checkout's `keel-runtime/`), used only when no
  `keel` command is found on `PATH` (spec FR-002).
- `--base-url`, `--executor`, `--credential-backend`, `--no-browser`: passed straight through to the
  launched `keel connect` invocation, unchanged, only when this script actually launches one (never
  sent to `status`). Omitted flags are simply not passed, leaving `keel-runtime` to apply its own
  defaults/config-file precedence.
- `--home` / `KEEL_HOME` (env, flag wins) / default `~/.keel`: the same precedence and default
  `keel-runtime` itself uses. Passed explicitly to every `status`/`connect` invocation this script
  makes, so the answer is never dependent on ambient environment differences between this script and
  its subprocess.
- `--wait-seconds` (default 8.0): how long to watch the launched process's log for a launch signal
  (FR-006) before reporting `authorization_pending_timeout`. Not part of the JSON shapes below, but
  documented here because it is the one knob that changes this script's own timing behavior; a
  caller with unusual latency needs (e.g. a test suite that wants this fast) may override it.
- Exits **0** for every outcome below except `internal_error`, which exits **1**. A non-zero exit
  from a usage error (unknown flag) is argparse's own behavior, printed to stderr, not part of this
  contract.
- Prints **exactly one line** of JSON to stdout, newline-terminated, nothing else on stdout -- a
  caller can safely `json.loads(subprocess.check_output(...))`.

## Output shapes (exhaustive)

**`runtime_unavailable`** -- neither a `keel` command on `PATH` nor a usable `--runtime-path`/
`KEEL_RUNTIME_PATH` directory was found. No process was launched.

```json
{"outcome": "runtime_unavailable", "message": "<explanation and remedy>"}
```

**`already_connected`** -- `keel-runtime status` (checked first, always) reported `running: true`.
No process was launched.

```json
{
  "outcome": "already_connected",
  "agent_session_id": "5b2e2f0a-9c3b-4b7e-8f3a-1e6c9b7a2d10",
  "base_url": "https://cloud.keel.example",
  "last_heartbeat_at": "2026-09-02T13:04:11.482Z"
}
```

**`authorization_started`** -- `status` reported not running; `keel connect` was launched detached
and, within the bounded wait, printed both `KEEL_USER_CODE=` and `KEEL_VERIFICATION_URI=` to its
log.

```json
{
  "outcome": "authorization_started",
  "user_code": "ABCD-1234",
  "verification_uri": "https://cloud.keel.example/device?code=ABCD-1234",
  "pid": 41213,
  "log_file": "/Users/ada/.keel/keel-connect-check.launch.log"
}
```

**`connected`** -- `status` reported not running; `keel connect` was launched detached and, within
the bounded wait, printed `KEEL_AGENT_SESSION_ID=` directly, with no `KEEL_USER_CODE=` line first --
a stored credential from a previous session was reused (keel-cloud spec 020's restart-reuse
behavior), so no human approval step was needed.

```json
{
  "outcome": "connected",
  "agent_session_id": "5b2e2f0a-9c3b-4b7e-8f3a-1e6c9b7a2d10",
  "pid": 41213,
  "log_file": "/Users/ada/.keel/keel-connect-check.launch.log"
}
```

**`authorization_pending_timeout`** -- `status` reported not running; `keel connect` was launched
detached, but neither signal above appeared in its log within `--wait-seconds`. The process is still
running in the background (it is not killed or considered failed) -- this outcome only means the
script stopped waiting, not that anything went wrong.

```json
{
  "outcome": "authorization_pending_timeout",
  "message": "keel connect did not report an authorization code or a connection within the wait window; it may still be starting -- check the log file or try again shortly.",
  "pid": 41213,
  "log_file": "/Users/ada/.keel/keel-connect-check.launch.log"
}
```

**`internal_error`** -- the located runtime's `status` subprocess did not honor its own documented
contract (crashed, produced non-JSON output, exited non-zero, or omitted the required `running`
key), or the `connect` subprocess could not be started at all. The sole outcome with a non-zero exit
code.

```json
{"outcome": "internal_error", "message": "<what went wrong>"}
```

## Guarantees a caller may rely on

1. Every key present in a given shape above is present in every occurrence of that shape -- no key
   is ever conditionally omitted within a shape.
2. No key outside these six shapes is ever added without this contract file changing first.
3. `status` is always checked before anything else runs; a `connect` process is launched if and only
   if `status` reported `running: false` at that moment (spec FR-003/FR-004). This script never
   launches a second `connect` process against a runtime it just found running.
4. `pid` and `log_file`, when present, name the actual detached `connect` process this invocation
   launched -- they are never stale or borrowed from an earlier run. A caller that wants to track or
   clean up the process this script started (as the `keel-cloud` E2E test does) may rely on `pid`
   being that process's real OS process id at the moment this script exits.
5. `outcome` is always one of the six values named above; a caller may safely dispatch on it without
   a default/unknown case swallowing a real answer silently -- an unrecognized `outcome` would itself
   indicate this contract was violated, which should never happen without this file changing first.
