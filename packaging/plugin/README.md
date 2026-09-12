# Keel Connect — a Claude Code plugin

One skill, two jobs. Say **"keel connect"** and the Keel runtime on this machine starts and hands
you a code and a URL to approve the device. Say **"keel disconnect"** and it stops, and is proved
gone. That is the whole plugin.

```bash
claude plugin marketplace add keeldiscovery/keel-marketplace
claude plugin install keel@keel
```

**Python 3.9 or newer is the one prerequisite**, and most machines already have it — macOS ships
3.9.6 with the command-line tools, Debian 11 ships 3.9, everything newer clears it. If yours does
not, the skill tells you the one install command for your operating system rather than failing.

**Nothing else is installed and nothing is downloaded.** The runtime travels inside the plugin, as
plain Python beside the script that runs it. There is no binary, no package index, no checksum and
no signature anywhere in this design.

## What it is not

- It does not run, validate or interpret any inference job. That is the connected runtime's
  business, entirely out of this plugin's view.
- It knows nothing about Keel's discovery protocol, MCP hosting, or any other Keel-branded skill.
- It carries no Keel Cloud address of its own. Which Keel you reach is the runtime's answer,
  relayed — every reply ends by naming it.
- It declares no hooks, no MCP servers and no configuration. A plugin that behaved differently
  from a plain copy of the same skill would be a plugin nobody could reason about.

## Where the real documentation lives

`skills/keel-connect/SKILL.md`, in this plugin. It is byte-for-byte the same file in every
packaging of this skill — this plugin, the Spec Kit extension, the Copilot repo drop and the bare
install — and a test asserts it.

Source, issues and the specs: https://github.com/keeldiscovery/keel-connect-skill

Privacy policy: https://keeldiscovery.com/privacy · Terms: https://keeldiscovery.com/terms. The
plugin adds no hooks, no MCP servers and no settings. The runtime it carries keeps its device
credential in a file under `~/.keel/` on this machine and speaks only to the Keel Cloud it names,
after you have approved the device in your browser.

Licensed under Apache-2.0.
