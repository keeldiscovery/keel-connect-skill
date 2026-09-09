# Implementation Plan: There is a door out

**Branch**: `002-keel-disconnect` | **Date**: 2026-09-09 | **Spec**: [spec.md](spec.md)

**Design of record**: keel-cloud `canon/designs/keel-disconnect-design.md` §10 step 5, with
`canon/designs/keel-skill-design.md` §11.

## Summary

One new script, one new contract, one new section of `SKILL.md`, and one new test module. The
script does three things: resolve the runtime through the module both scripts already share, run
that runtime's `disconnect`, and translate its four documented outcomes into the six a founder's
agent is told about. There is no signalling, no waiting, no heartbeat handling and no process
management anywhere in this repository -- all of that is keel-runtime's, behind a contract, and
the whole point of step 5 landing after step 2.

The one thing worth naming as *design* rather than plumbing is `SKILL.md`'s ambiguity rule: the
connect check is the only one of the two scripts that can act on a misread in a way the founder
then has to undo, so it is the one that never runs on a guess.

## Technical Context

**Language/Version**: Python 3.9+, standard library only. `scripts/keel_disconnect.py` uses
`argparse`, `json`, `os`, `subprocess`, `sys` and nothing else, and is written in the same
pre-3.9 syntax its sibling is -- no f-strings, no annotations -- so an old interpreter running it
gets an answer rather than a `SyntaxError`.

**Primary Dependencies**: none. The tests add `http.cookiejar`/`urllib` for the one real
end-to-end walk, both stdlib.

**Storage**: none. This script writes no file at all -- not even a log. The one file that changes
during a disconnect is the runtime's own heartbeat, removed by the runtime or by its own
`disconnect`, never by this script.

**Testing**: `python3 -m unittest discover tests`, a second module beside the first. Every outcome
through both resolution branches against the fake runtimes, plus `RealDisconnectTestCase`, which
skips itself when no keel-cloud is listening.

**Target Platform**: macOS/Linux primary, Windows by the same code path -- there is no POSIX-only
call in this script, because every signal is the runtime's to send.

**Performance Goals**: bounded by the runtime's own 15-second worst case, plus a subprocess
timeout of 45 seconds that exists only to catch a runtime not honouring it at all.

**Constraints**: stdlib only; no network; no credential; no launch path; exactly one line of JSON.

## Decisions this plan made, that the design left open

**`--home` when nothing was given.** The disconnect design's §5.2 says "`--home` / `KEEL_HOME` /
default `~/.keel`: resolved by this script and passed explicitly". Since keel-runtime's spec
`004-shipped-runtime` the home follows the address (skill design §6.3), so a guessed `~/.keel`
would name a **different** directory from the one the sibling script connected on -- the door out
would not open on the door in. The rule kept is §5.2's *intent* -- one home, resolved once, never
left to ambient differences between this script and its subprocess -- expressed the way its
sibling now expresses it: pass `--home` only when given one, and otherwise let the runtime resolve
the same home it always does. Documented in the contract's *Invocation*, with the deviation named.

**No `python_too_old`, and no version gate.** Six outcomes is what the contract says, exhaustively.
A seventh here would put a shape in one script that the other's contract does not have, for a case
that is already handled: a founder reaches this skill through a connect first, and that script
gates the interpreter. What this file does instead is stay parseable by any Python 3, so the old
interpreter gets an answer rather than a traceback.

**A 45-second subprocess timeout.** The command bounds itself at 15 seconds by its own contract.
45 is three times that, chosen so the timeout can only fire for a runtime that is not honouring
the contract at all -- which is `internal_error`, not something to keep waiting for.

**Which keys come up, and which do not.** The runtime's contract puts `home`, `base_url` and
`environment` on all four of its shapes. Only `environment` is carried up: one key for which Keel,
never two (skill design §7), and guarantee 2 forbids a key outside a documented shape. A caller
who wants the home knows it already -- it is the one they passed, or the one their `status` names.

**`SKILL.md`'s frontmatter, finished here.** Spec 003 deliberately left it alone. This spec is
where both jobs exist, so this is where a trigger-first description naming both can be written
without being wrong for a week: `name`, `description`, `license`, nothing else (skill design
decisions 5 and 6). `user-invocable` and `disable-model-invocation` are dropped -- one host's
private extensions in a file every host reads.

**One real end-to-end test, in this repository.** The design's §8.2 gives this repository fakes and
gives the real walk to keel-e2e-eval (step 6). Both still stand -- but the runtime now travels
*inside this skill*, so this repository can prove its own door without a referee, and a spec that
ships a stop button without ever having stopped a real process is a spec that hopes. The test
skips itself when no keel-cloud is listening, so CI and every offline run are unaffected. Its one
cost is named in its docstring: `approve_device` speaks keel-cloud's wire to stand in for the
founder's browser click, and it is the only place in this repository that knows that wire exists.

**A third fake-runtime fixture.** `fake_runtime_no_disconnect/` exists for exactly one assertion:
that the old-runtime path into `internal_error` is a real `argparse` failure, not a mock of one.
The design asks for it in those words (§8.2).

## Constitution Check

- **One skill, one repository.** No second skill, no second `SKILL.md`, no rename. The skill of the
  connection, both directions (design decision 8).
- **The JSON is the only interface.** A second contract file, in the sibling's five-part shape,
  with its own guarantees.
- **No part of the runtime is re-implemented here.** Not the signals, not the bounds, not the
  heartbeat. This repository shells a documented command.
- **No ecosystem and no host name** in `SKILL.md` or the scripts, beyond the one marked exception
  that already exists.

## Project Structure

```
scripts/
  _runtime_location.py          unchanged -- used whole by both scripts now
  keel_connect_check.py         unchanged
  keel_disconnect.py            new
specs/002-keel-disconnect/
  spec.md  plan.md  tasks.md
  contracts/skill-disconnect-output.md
tests/
  test_keel_disconnect.py       new
  fixtures/fake_runtime_path/keel_runtime/__main__.py     + disconnect
  fixtures/fake_runtime_on_path/keel                      + disconnect
  fixtures/fake_runtime_no_disconnect/keel_runtime/       new -- deliberately without one
SKILL.md                        frontmatter finished; second job, replies, ambiguity rule
```

## Complexity Tracking

None. The script is 200 lines of translation with no state, no timing and no I/O beyond one
subprocess. The only thing in this spec that could have been complicated -- proving a process is
gone -- lives one repository down, behind a contract, on purpose.
