---
name: "keel-connect"
description: "Check whether the user's local Keel runtime (keel-runtime) is connected to Keel Cloud, and start it if it isn't. Invoke this whenever the user types or clearly means \"keel connect\" -- including phrasings like \"connect keel\", \"start the keel runtime\", \"launch keel connect\", \"is keel connected\", or \"check keel's status\". This skill only understands the local keel-runtime process; it has no knowledge of Keel's discovery protocol, MCP, or any other Keel-branded skill."
user-invocable: true
disable-model-invocation: false
---

## What this skill does

One job: decide whether a `keel-runtime` process is already running and connected to Keel Cloud
on this machine, and if not, start `keel connect` for the user and hand back what they need to
approve it. Nothing here understands what a connected runtime is *for* -- that is Keel Cloud's and
the runtime's own business, not this skill's.

All of the actual logic lives in one deterministic script,
`scripts/keel_connect_check.py` (path resolved relative to this `SKILL.md`'s own directory). Run
it, parse its one line of JSON, and follow the instructions below for the `outcome` you get back.
Its full, stable contract is documented in
`specs/001-keel-connect-check/contracts/skill-script-output.md` -- read that file if anything below
is ambiguous; it is the source of truth, this section is a summary for quick use.

## Running the check

```bash
python3 <this skill's directory>/scripts/keel_connect_check.py
```

No flags are required for the common case -- the script tries a `keel` command on `PATH` first (the
normal, installed case), then falls back to `--runtime-path`/`KEEL_RUNTIME_PATH` for a development
checkout. If the user has mentioned working against a local `keel-cloud` checkout (rather than an
installed `keel-runtime`), or a first attempt reports `runtime_unavailable`, you may retry with:

```bash
python3 <this skill's directory>/scripts/keel_connect_check.py \
    --runtime-path <path-to-a-keel-cloud checkout>/keel-runtime
```

Do not pass any other flags unless the user has specifically told you their Keel Cloud base URL,
preferred executor, or credential backend -- the script and the runtime already know sensible
defaults.

## Interpreting each outcome

The script prints exactly one line of JSON with an `outcome` key. Match it against the six values
below and reply to the user in plain language -- never show them the raw JSON.

**`already_connected`** -- a runtime is already running and connected. Nothing was started.
> Tell the user Keel is already connected. You may mention the `agent_session_id` if useful context,
> but it's rarely something a human needs to see.

**`connected`** -- nothing was running, so this check started `keel connect`, and it connected
immediately using a saved credential from a previous session -- no approval was needed.
> Tell the user Keel just reconnected on its own using a saved credential; no action needed from
> them.

**`authorization_started`** -- nothing was running, `keel connect` was started, and it is now
waiting for the user to approve this device.
> Relay the `user_code` and `verification_uri` to the user verbatim -- tell them to open the URL
> (or visit it and enter the code) to approve. Mention they can just say "keel connect" again in a
> little while to confirm it went through once they've approved it.

**`authorization_pending_timeout`** -- nothing was running, `keel connect` was started, but it
hadn't printed an authorization code (or connected) yet by the time this check stopped waiting. The
process is still running in the background, not dead and not abandoned.
> Tell the user the runtime is starting up but hasn't shown an authorization code yet -- ask them to
> wait a few seconds and say "keel connect" again, which will either show the code now or (if it
> already connected in the meantime) confirm the connection.

**`runtime_unavailable`** -- no `keel` command was found on `PATH`, and no usable
`--runtime-path`/`KEEL_RUNTIME_PATH` checkout was found either.
> Relay the script's `message` to the user in your own words -- they likely need to install
> `keel-runtime`, or, if they're working from a local `keel-cloud` checkout, tell you (or set
> `KEEL_RUNTIME_PATH`) where it lives so you can retry with `--runtime-path`.

**`internal_error`** -- something broke that isn't a normal "not connected" situation: the located
runtime's `status` subprocess didn't answer the way it's supposed to, or `keel connect` couldn't
even be started.
> Tell the user something unexpected happened, share the `message`, and suggest they check their
> Keel installation directly (e.g. run `keel status` or `keel connect` themselves in a terminal) --
> don't guess at a fix on their behalf.

## What this skill deliberately does not do

- It does not run, validate, or interpret any inference job -- that's the connected runtime's job,
  entirely out of this skill's view.
- It does not know anything about Keel's discovery protocol, MCP hosting, or the unrelated
  `keel-discovery` skill in the separate `keel-skill` repository. Do not reach for anything from
  that skill while handling a "keel connect" request -- they share a product name and nothing else.
- It never waits on human approval itself (that's an out-of-band step the user takes in their
  browser) -- it only reports whether that wait has a code to show yet.
