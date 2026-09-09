# Contract: `keel_disconnect.py` CLI output

**This is the stable, external contract** -- the one thing `SKILL.md` (and anything else that
shells out to this script, including keel-e2e-eval's `make down` and S-001's tail) is allowed to
depend on. Everything else about this script's implementation (its subprocess timeout, its helper
names, how it phrases an `internal_error`) may change; this contract may not, without this file
changing first.

Design of record: keel-cloud `canon/designs/keel-disconnect-design.md` §5.2, with §11 of
`canon/designs/keel-skill-design.md`. Written in the same five parts as its sibling
`specs/001-keel-connect-check/contracts/skill-script-output.md`, and read by the same callers.
**A change to this file is a major version bump of the skill**, the same rule that governs that
one; it is one of exactly two things that can be one.

This script is itself a caller of the runtime's own stable contract (keel-runtime
`specs/003-keel-disconnect/contracts/disconnect-cli-output.md`) -- this file documents a distinct,
one-level-higher contract, not a restatement of that one. Two outcome names appear in **both**
this file and the connect script's, and carry one shape and one meaning each: `runtime_unavailable`
and `internal_error`, the two ways the layer *between* the skill and the runtime can fail. No third
name collides.

## Invocation

```text
python3 <skill root>/scripts/keel_disconnect.py [--home PATH]
```

- **No flag is required for the normal case.** The runtime travels inside the skill
  (`<skill root>/keel_runtime/`) and is run with the interpreter that ran this script.
- `--home` / `KEEL_HOME` (env, flag wins): passed to `disconnect` **only when it was given**, and
  resolved by exactly the code path `keel_connect_check.py` resolves it with. When neither is set,
  the runtime resolves its own home from the Keel it resolves (`~/.keel/<host-slug>/`) -- the same
  home its own `status` and `connect` resolve from the same inputs, which is what makes this door
  out open on the door in. **This script does not guess a home.**
  *(The design's §5.2 wrote this rule as "flag > `KEEL_HOME` > `~/.keel`, resolved by this script
  and passed explicitly". Since keel-runtime's spec `004-shipped-runtime` the home follows the
  address (keel-skill-design.md §6.3), so a guessed `~/.keel` would name a **different** directory
  from the one the sibling script connected on. The intent of §5.2 -- one home, resolved once, not
  left to ambient differences between this script and its subprocess -- is what is kept.)*
- `--runtime-path` / `KEEL_RUNTIME_PATH` (env, flag wins): **a development override**, identical in
  meaning and precedence to the connect script's, and not part of what a founder or a host is ever
  told about. Hidden from `--help` for that reason.
- Exits **0** for every outcome below except `internal_error`, which exits **1** -- the same rule
  the connect script follows, and the reason `keel disconnect` itself does not need a non-zero
  exit: **the script is the layer that decides what counts as broken.**
- Prints **exactly one line** of JSON to stdout, newline-terminated, nothing else on stdout -- a
  caller can safely `json.loads(subprocess.check_output(...))`.
- Makes **no network call**, starts **no process**, and touches **no credential**. It stops a
  process; it does not forget a machine. A later "keel connect" on the same home reconnects with no
  device code and no browser.
- There is no `python_too_old` here and there cannot be: this script is reached only through the
  same skill whose connect script gates the interpreter, and its six outcomes below are exhaustive.
  It is written in the same pre-3.9 syntax its sibling is, so an old interpreter running it
  directly gets an answer rather than a `SyntaxError`.

## Which runtime runs

The same three rules, in the same order, from the same `scripts/_runtime_location.py` both scripts
import -- used **whole** here, since there is no branch this script must skip. See the connect
script's contract for the order and the reasoning; there is one resolution rule in this skill and
one place it is written down.

## Output shapes (exhaustive)

`environment` is on **all six**: *which Keel this is* -- `"cloud"` for the built-in default, or
`"host:port"` as the runtime resolved it. When the heartbeat was readable it describes the Keel the
**stopped process** was connected to (its own record), not what a fresh resolution would pick now.
It is `null` when nothing names a Keel at all, and on the two outcomes where no runtime answered.
The script carries no base URL and no environment table of its own: it relays what the runtime
handed it, and says nothing rather than guessing (invariant X-5).

The runtime's `home` and `base_url` keys are deliberately **not** carried up. `environment` is the
one key for *which Keel*, never two.

**`disconnected`** -- `keel disconnect` reported `stopped`. The runtime was running, was signalled,
and has been **observed** gone. It is a proof, not a send-and-hope.

```json
{"outcome": "disconnected", "pid": 41213, "waited_ms": 84, "signal": "SIGTERM", "environment": "cloud"}
```

`signal` is `"SIGTERM"` when the runtime left within its grace and `"SIGKILL"` when it had to be
escalated. `waited_ms` is measured from the first signal, so a caller can see the difference
between a runtime that stopped in 80ms and one that took nine seconds to leave a job.

**`not_running`** -- reported `not_running`. Nothing was running on this home; nothing was done.
A missing heartbeat, an unreadable one, a malformed one and one short a required field are all this
one answer.

```json
{"outcome": "not_running", "environment": "cloud"}
```

**`stale_pid_cleared`** -- reported `stale_pid_cleared`. A heartbeat left behind by a runtime that
died without cleaning up -- a crash, a `SIGKILL`, a lost power supply. The file was removed and
**no process was signalled**.

```json
{"outcome": "stale_pid_cleared", "pid": 40118, "environment": "cloud"}
```

**`did_not_stop`** -- reported `timeout`. The process survived `SIGTERM` and `SIGKILL` inside the
15-second bound and **is still polling**; the heartbeat was deliberately left in place, so `status`
keeps reporting the process that is still there.

```json
{
  "outcome": "did_not_stop",
  "pid": 41213,
  "waited_ms": 15003,
  "message": "the keel-runtime process did not exit after SIGTERM and SIGKILL; it is stuck in a call the operating system will not interrupt.",
  "environment": "cloud"
}
```

**`runtime_unavailable`** -- no checkout, no `keel_runtime/` beside the skill, and no `keel` on
`PATH`. Nothing was run. Same shape, same message discipline and the same meaning as the connect
script's.

```json
{"outcome": "runtime_unavailable", "message": "<explanation and remedy>", "environment": null}
```

**`internal_error`** -- the located runtime's `disconnect` did not honour its own contract: it
crashed, exited non-zero, printed something other than one JSON line, answered without `outcome`,
answered an outcome this skill does not know -- or, the likeliest cause in practice, **it is a
keel-runtime old enough not to have a `disconnect` subcommand at all**, in which case argparse
exits 2 with a usage line on stderr. The message names that case explicitly, because "update your
keel-runtime" is a remedy and "something went wrong" is not. The sole non-zero exit.

```json
{"outcome": "internal_error", "message": "<what went wrong>", "environment": null}
```

## Guarantees a caller may rely on

1. **Exactly one line of JSON on stdout, always**, for all six outcomes, and nothing else on
   stdout. Every key present in a shape above is present in **every** occurrence of that shape --
   no key is ever conditionally omitted within a shape.
2. **No key outside these six shapes is added without this contract file changing first.**
3. **This script never starts a `keel connect`, under any outcome. It is not capable of it** --
   there is no launch path in it (invariant S3).
4. `pid`, where present, is the pid this home's heartbeat named at the moment the script ran. Only
   a pid read from that file is ever signalled; there is no way to hand this script a pid to kill.
5. `outcome` is always one of the six values above, and **exit 0 for every one of them except
   `internal_error`, which exits 1.** One rule, no exceptions.
6. **`environment` is present on all six shapes**, and is `null` when no runtime answered.
7. `disconnected` is emitted only after the pid was observed **not alive**. A caller told
   `disconnected` may start a new runtime on this home immediately, with no risk of two runtimes
   against one credential. A caller told `did_not_stop` must **not**: the old one is still claiming
   jobs (invariant S2).
8. **No outcome touches the credential**, and no outcome makes a network call.

## Why the runtime's four names become six

`not_running` and `stale_pid_cleared` mean the same thing at both levels and keep their names.
`stopped` becomes `disconnected` and `timeout` becomes `did_not_stop` because the skill layer
speaks the founder's vocabulary, not the process's -- the connect script already does this, turning
`running: true` into `already_connected` -- and because "timeout" at this level is ambiguous
between the runtime's grace bound and this script's own subprocess timeout.

The other two, `runtime_unavailable` and `internal_error`, have no counterpart below them: they are
the two ways the layer *between* the skill and the runtime can fail, and the connect script already
owns them under exactly those names.

| keel-runtime `disconnect` | this script |
|---|---|
| `stopped` | `disconnected` |
| `not_running` | `not_running` |
| `stale_pid_cleared` | `stale_pid_cleared` |
| `timeout` | `did_not_stop` |
| — (no runtime resolved) | `runtime_unavailable` |
| — (the contract was broken) | `internal_error` |
