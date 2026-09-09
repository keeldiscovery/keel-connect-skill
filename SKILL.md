---
name: "keel-connect"
description: "Check whether the user's local Keel runtime (keel-runtime) is connected to Keel Cloud, and start it if it isn't. Invoke this whenever the user types or clearly means \"keel connect\" -- including phrasings like \"connect keel\", \"start the keel runtime\", \"launch keel connect\", \"is keel connected\", or \"check keel's status\". This skill only understands the local keel-runtime process; it has no knowledge of Keel's discovery protocol, MCP, or any other Keel-branded skill."
user-invocable: true
disable-model-invocation: false
---

## What this skill does

One job: decide whether a Keel runtime is already running and connected to Keel Cloud on this
machine, and if not, start it for the user and hand back what they need to approve it. Nothing here
understands what a connected runtime is *for* -- that is Keel Cloud's and the runtime's own
business, not this skill's.

**The runtime travels inside this skill.** `keel_runtime/` sits beside `scripts/`, and the script
runs it with the interpreter that ran the script. Nothing is downloaded and nothing has to be
installed. The one thing the user might not already have is a Python 3.9 or newer.

All of the actual logic lives in one deterministic script, `scripts/keel_connect_check.py` (path
resolved relative to this `SKILL.md`'s own directory). Run it, parse its one line of JSON, and
follow the instructions below for the `outcome` you get back. Its full, stable contract is
`specs/001-keel-connect-check/contracts/skill-script-output.md` -- read that file if anything below
is ambiguous; it is the source of truth and this is a summary for quick use.

## Running the check

```bash
python3 <this skill's directory>/scripts/keel_connect_check.py
```

<!-- D5 exception, deliberate and the only one in this file: the line below names an agent host,
     which no *reply* to a user ever may. It is an instruction to the agent, not a sentence anyone
     reads. -->
If you are GitHub Copilot, add `--host copilot`.

No other flag is required, or wanted. Do not pass a base URL, an executor or a credential backend
unless the user has specifically told you theirs -- the script and the runtime already know
sensible defaults, and a flag you guessed will outrank the user's own configuration.

**If `python3` is not found at all**, the user has no Python, and no script can tell you so -- the
command simply fails. Tell them Keel needs Python 3.9 or newer, installed once: on macOS
`xcode-select --install`, or https://www.python.org/downloads/; on Windows
`winget install Python.Python.3.12`, or Python from the Microsoft Store; on Linux their package
manager, e.g. `sudo apt install python3`. Then ask them to say "keel connect" again.

## Interpreting each outcome

The script prints exactly one line of JSON with an `outcome` key. Match it against the seven values
below and reply in plain language -- **never show the raw JSON**.

Every outcome also carries `environment`: which Keel this is. **End your reply with one clause
naming it** -- "on Keel Cloud", or "on `localhost:18081`" written exactly as given. When it is
`null` no runtime answered, so say nothing about which Keel; do not guess one.

**`already_connected`** -- a runtime is already running and connected. Nothing was started.
> Tell the user Keel is already connected. You may mention the `agent_session_id` as context, but
> it is rarely something a human needs to see.

**`connected`** -- nothing was running, so the check started the runtime, and it connected
immediately using a saved credential from a previous session -- no approval was needed.
> Tell the user Keel just reconnected on its own using a saved credential; no action needed from
> them.

**`authorization_started`** -- nothing was running, the runtime was started, and it is now waiting
for the user to approve this device.
> Relay the `user_code` and `verification_uri` **verbatim** -- do not shorten, rewrite or rebuild
> the URL; the Keel that issued it is the only thing that knows where its own approval screen is.
> Tell them to open it and approve, and that they can just say "keel connect" again in a little
> while to confirm it went through.

**`authorization_pending_timeout`** -- the runtime was started, but it had not printed an
authorization code (or connected) by the time the check stopped waiting. The process is still
running in the background: not dead, not abandoned.
> Tell the user the runtime is starting but has not shown a code yet -- ask them to wait a few
> seconds and say "keel connect" again, which will either show the code now or confirm the
> connection if it completed in the meantime.

**`python_too_old`** -- the Python that ran the check is older than 3.9. Nothing was resolved and
nothing was started.
> Relay the `message` -- it already names the version they have, the version Keel needs, and the
> one install command for their operating system. Tell them it is a one-time install, and to say
> "keel connect" again afterwards. Do not offer a workaround; there isn't one.

**`runtime_unavailable`** -- the runtime that is supposed to travel inside this skill is not there,
and no `keel` command was found either.
> Relay the `message` in your own words: the skill directory looks incomplete, so they should
> reinstall or re-copy it in full. This is a broken installation, not something the user forgot to
> do -- do not tell them to install anything from a package index.

**`internal_error`** -- something broke that is not a normal "not connected" situation: the
runtime's `status` did not answer the way it is supposed to, or the runtime could not be started at
all. This is the only outcome that exits non-zero.
> Tell the user something unexpected happened, share the `message`, and suggest they check their
> Keel installation directly. Do not guess at a fix on their behalf.

## What this skill deliberately does not do

- It does not run, validate, or interpret any inference job -- that is the connected runtime's job,
  entirely out of this skill's view.
- It does not know anything about Keel's discovery protocol, MCP hosting, or any other Keel-branded
  skill. Do not reach for anything from one while handling a "keel connect" request.
- It never waits on human approval itself (that is an out-of-band step the user takes in their
  browser) -- it only reports whether that wait has a code to show yet.
- It carries no Keel Cloud address of its own. Which Keel a user reaches is the runtime's answer,
  relayed; never construct, complete or correct a URL it hands you.
