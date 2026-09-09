# Keel Connect, committed into this repository

`.github/skills/keel-connect/` is an agent skill. Commit it, and everyone who works in this
repository has it on their next `git pull` — reviewed like code, the same for everyone, needing no
installer, no marketplace and no network.

This is the only packaging of Keel's skill that reaches a repository rather than one laptop, and
therefore the only one that reaches the coding agent and the editor's chat for **everybody** on the
team at once.

## What it does

One skill, two jobs. Someone says **"keel connect"**, and the Keel runtime on their machine starts
and hands back a code and a URL to approve the device. Someone says **"keel disconnect"**, and it
stops, and is proved gone. Every reply names which Keel it is talking to.

## What it needs

**Python 3.9 or newer, and nothing else.** Most machines already have it — macOS ships 3.9.6 with
the command-line tools, Debian 11 ships 3.9. Anyone whose machine does not gets one sentence naming
the install command for their operating system, rather than a failure.

The runtime itself travels inside this directory as plain Python. Nothing is downloaded, nothing is
installed, and there is no binary, package index, checksum or signature involved.

## For one machine rather than one repository

The same skill installs personally, from the bare distribution:

```sh
./install.sh --host copilot            # ~/.copilot/skills/
./install.sh --host copilot --project  # ./.github/skills/  -- what this directory already is
./install.sh --host agents             # ~/.agents/skills/  -- read by more than one agent
```

## Where the real documentation lives

`.github/skills/keel-connect/SKILL.md`, in this drop. It is byte-for-byte the same file in every packaging of
this skill, and a test asserts it.

Source, issues and the specs: https://github.com/keeldiscovery/keel-connect-skill

Licensed under Apache-2.0.
