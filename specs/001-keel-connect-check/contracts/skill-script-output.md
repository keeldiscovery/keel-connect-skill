# Contract: `keel_connect_check.py` CLI output

**This is the stable, external contract** -- the one thing `SKILL.md` (and anything else that
shells out to this script, including the cross-repo E2E test in `keel-cloud`) is allowed to depend
on. Everything else about this script's implementation (the log file's name, the exact poll
interval, internal helper function names) may change; this contract may not, without this file
changing first.

**Rewritten once by spec `003-bundled-runtime`** for **seven** outcomes, from six: `python_too_old`
is new, and `environment` is now a key on every shape. Design of record: keel-cloud
`canon/designs/keel-skill-design.md` §7. **A change to this file is a major version bump of the
skill, and the only thing that can be one.**

**Amended (bugfix, no version bump)**: `already_connected` was being said for `running: true`
alone, before keel-runtime commit `bfc0ad6` made that no longer imply approval was done. This
amendment corrects the precondition this file already documented for that shape (`status`
reporting the runtime running) to what the shape's own name always meant -- `connected: true` too
-- and widens `authorization_started` and `authorization_pending_timeout` to also be reached by
re-reading an existing launch log rather than only by a fresh launch. **No shape gains, loses, or
renames a key**; the seven shapes and every key on them are unchanged, which is why this is not the
major version bump the rule above describes.

This script is itself a caller of the runtime's own stable contract (keel-cloud
`specs/021-keel-runtime-status/contracts/status-cli-output.md`) -- this file documents a distinct,
one-level-higher contract, not a restatement of that one.

## Invocation

```text
python3 <skill root>/scripts/keel_connect_check.py
    [--host {claude,copilot,auto}] [--base-url URL] [--executor NAME]
    [--credential-backend {auto,file,keyring}] [--no-browser] [--home PATH]
    [--wait-seconds SECONDS]
```

- **No flag is required for the normal case.** The runtime travels inside the skill
  (`<skill root>/keel_runtime/`) and is run with the interpreter that ran this script.
- `--host` (default `auto`): which agent host is running the check. `auto` reads the environment
  this process was launched into and answers one host, or nothing at all when that environment is
  silent or names two at once. The answer is passed to the launched `connect` as `--executor`, and
  **only** then: never on a `status` call, never when `--executor` was given, and never when the
  detection is silent or ambiguous. **No outcome shape changes because of it.**
- `--base-url`, `--executor`, `--credential-backend`, `--no-browser`: passed straight through to
  the launched `connect` invocation, unchanged, only when this script actually launches one (never
  sent to `status`). Omitted flags are simply not passed, leaving the runtime to apply its own
  defaults and config-file precedence. `--executor`, when given, wins over `--host` outright.
- `--home` / `KEEL_HOME` (env, flag wins): passed to `status` and `connect` **only when it was
  given**. When neither is set the runtime derives its own home from the Keel it resolved
  (`~/.keel/<host-slug>/`) and reports it back; this script relays that home and puts the launch
  log in it. It no longer guesses a default of its own.
- `--wait-seconds` (default 8.0): how long to watch the launched process's log for a launch signal
  before reporting `authorization_pending_timeout`. Not part of the JSON shapes below, but
  documented here because it is the one knob that changes this script's own timing behaviour.
- `--runtime-path` / `KEEL_RUNTIME_PATH` (env, flag wins): **a development override**, and not part
  of what a founder or a host is ever told about. It names a keel-runtime checkout directory and it
  wins over the bundled runtime, so a developer debugging the runtime is not silently testing a
  release. It is hidden from `--help` for that reason.
- Exits **0** for every outcome below except `internal_error`, which exits **1**. A non-zero exit
  from a usage error (unknown flag) is argparse's own behaviour, printed to stderr, not part of
  this contract.
- Prints **exactly one line** of JSON to stdout, newline-terminated, nothing else on stdout -- a
  caller can safely `json.loads(subprocess.check_output(...))`.

## Which runtime runs

Three rules, in this order (design §3.2). The `source` is not reported in any outcome; it is
documented here because it is what the outcomes below are *about*.

1. **a checkout** -- `--runtime-path` / `KEEL_RUNTIME_PATH`, when it holds a
   `keel_runtime/__main__.py`. Run as `<this interpreter> -m keel_runtime`.
2. **the runtime that travelled with this skill** -- `<skill root>/keel_runtime/`. Same
   invocation. This is the normal case.
3. **a `keel` on `PATH`** -- someone installed or packaged one themselves.

**The bundled copy beats a `keel` on `PATH`**, which reverses spec 001's order: the bundled copy
*is* the skill -- the runtime this skill's own tests ran against -- and a stranger's `keel` must
not shadow it silently.

## Output shapes (exhaustive)

`environment` is on **all seven**: *which Keel this is* -- `"cloud"` for the built-in default, or
`"host:port"` as the runtime resolved it. It is `null` **exactly when no runtime answered** --
`python_too_old`, `runtime_unavailable`, and an `internal_error` raised before `status` returned.
The script carries no base URL and no environment table of its own: it relays what the runtime
handed it, and says nothing rather than guessing.

**`python_too_old`** -- the interpreter running this script is below Python 3.9. **Nothing was
resolved and nothing was run.** This is the first thing the script decides, above every import but
`sys`, so a founder on an old interpreter gets a sentence rather than a `SyntaxError`.

```json
{
  "outcome": "python_too_old",
  "found": "3.8",
  "required": "3.9",
  "environment": null,
  "message": "Keel needs Python 3.9 or newer; this is Python 3.8. Install it once and say \"keel connect\" again: run `xcode-select --install`, or get it from https://www.python.org/downloads/"
}
```

The `message` names the version found, the version needed, and one install command for the
operating system this is running on -- macOS, Windows, or a package manager otherwise. There is no
`python_missing` outcome and there cannot be: a script that cannot start cannot emit one. With no
`python3` at all the host gets *command not found*, and that answer lives in `SKILL.md` and
`README.md` instead.

**`runtime_unavailable`** -- no checkout, no `keel_runtime/` beside the skill, and no `keel` on
`PATH`. No process was launched.

```json
{"outcome": "runtime_unavailable", "message": "<explanation and remedy>", "environment": null}
```

The `message` names neither `--runtime-path` nor `KEEL_RUNTIME_PATH` (they are development
overrides) and no longer offers `pip install keel-runtime`: nothing is installed any more, so a
skill with no runtime beside it is a skill that was copied wrong, not a founder who skipped a step.

**`already_connected`** -- `status` (checked first, always) reported `running: true` **and
`connected: true`**. No process was launched.

keel-runtime commit `bfc0ad6` (keel-cloud `specs/021-keel-runtime-status/contracts/
status-cli-output.md` guarantee 4) means `running: true` no longer implies approval is done: a
`connect` writes its heartbeat, and so is alive and pid-checkable, from the moment it starts, well
before a human has approved the device. `running: true` with `connected: false` is **not**
`already_connected` -- see `authorization_started` and `authorization_pending_timeout` below, both
of which this script also reaches without launching anything, by re-reading a launch log already on
disk.

```json
{
  "outcome": "already_connected",
  "agent_session_id": "5b2e2f0a-9c3b-4b7e-8f3a-1e6c9b7a2d10",
  "last_heartbeat_at": "2026-09-02T13:04:11.482Z",
  "environment": "cloud"
}
```

**This shape lost `base_url` and gained `environment`** -- one key for *which Keel*, never two.
That is the only change to a shape that already existed.

**`authorization_started`** -- either `status` reported not running and `connect` was launched
detached and, within the bounded wait, printed both `KEEL_USER_CODE=` and `KEEL_VERIFICATION_URI=`
to its log; **or** `status` reported `running: true` and `connected: false` (approval still
pending) and those same two lines were already sitting in the launch log an earlier call (or the
runtime itself) wrote -- nothing is launched a second time. Both reach the identical shape below;
a caller cannot tell from the JSON alone which one happened, and does not need to -- the code and
URL are the same code and URL either way.

```json
{
  "outcome": "authorization_started",
  "user_code": "ABCD-1234",
  "verification_uri": "https://cloud.keel.example/device?code=ABCD-1234",
  "pid": 41213,
  "log_file": "/Users/ada/.keel/cloud.keel.example/keel-connect-check.launch.log",
  "environment": "cloud"
}
```

`verification_uri` is relayed **verbatim**. The keel-cloud that issued it is the only thing that
knows where its own approval screen lives, so nothing here may normalise, shorten or rebuild it.

**`connected`** -- `status` reported not running; `connect` was launched detached and, within the
bounded wait, printed `KEEL_AGENT_SESSION_ID=` with no `KEEL_USER_CODE=` line first -- a stored
credential was reused, so no human approval step was needed.

```json
{
  "outcome": "connected",
  "agent_session_id": "5b2e2f0a-9c3b-4b7e-8f3a-1e6c9b7a2d10",
  "pid": 41213,
  "log_file": "/Users/ada/.keel/cloud.keel.example/keel-connect-check.launch.log",
  "environment": "cloud"
}
```

**`authorization_pending_timeout`** -- either `status` reported not running, `connect` was
launched detached, and neither signal above appeared in its log within `--wait-seconds`; **or**
`status` reported `running: true` and `connected: false` and the launch log on disk (an earlier
call's, or absent entirely) has no `KEEL_USER_CODE=` in it -- a stored-credential reconnect in
progress, not a device approval waiting on this founder. Either way the process is still running in
the background (it is not killed and not considered failed) -- this outcome means the script has
nothing new to report, not that anything went wrong.

```json
{
  "outcome": "authorization_pending_timeout",
  "message": "keel connect did not report an authorization code or a connection within the wait window; it may still be starting -- check the log file or try again shortly.",
  "pid": 41213,
  "log_file": "/Users/ada/.keel/cloud.keel.example/keel-connect-check.launch.log",
  "environment": "cloud"
}
```

**`internal_error`** -- the located runtime's `status` did not honour its own documented contract
(crashed, produced non-JSON output, exited non-zero, or omitted the required `running` key), or the
`connect` subprocess could not be started at all. The sole outcome with a non-zero exit code.

```json
{"outcome": "internal_error", "message": "<what went wrong>", "environment": null}
```

`environment` is `null` when `status` never returned, and carries the runtime's answer when the
failure came later (a `connect` that would not start).

## Guarantees a caller may rely on

1. **Exactly one line of JSON on stdout, always**, for all seven outcomes, and nothing else on
   stdout.
2. **Exit 0 for every outcome except `internal_error`, which exits 1.** One rule, no exceptions.
3. `outcome` is one of the seven values above, and **no key outside a shape is added without this
   file changing first**. Every key listed for a shape is present in every occurrence of it -- no
   key is ever conditionally omitted within a shape.
4. **`environment` is present on all seven shapes**, and is `null` exactly when no runtime
   answered.
5. `status` is always checked before anything is launched; a `connect` process is launched if and
   only if `status` reported `running: false` at that moment. This script never launches a second
   `connect` against a runtime it just found running, and `pid`/`log_file` are never stale or
   borrowed from an earlier run -- a caller that wants to track or clean up the process this script
   started may rely on `pid` being that process's real OS process id at the moment this script
   exits.

## What changed from spec 001's six shapes

| | Then | Now |
|---|---|---|
| `python_too_old` | — | new, and reachable before anything is resolved |
| `environment` | — | on all seven shapes |
| `already_connected.base_url` | present | **gone**, replaced by `environment` |
| resolution order | `PATH`, then a checkout | a checkout, then **bundled**, then `PATH` |
| `runtime_unavailable.message` | named `pip install keel-runtime` | names neither an install nor the development override |
| `--home` default | `~/.keel`, guessed by the script | the runtime derives and reports it |
| `--host` | — | new; changes no shape |

The three outcome names spec 001 shipped that are unchanged in shape -- `connected`,
`authorization_started`, `authorization_pending_timeout` -- gained `environment` and nothing else.
