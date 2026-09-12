# keel-marketplace

A Claude Code plugin marketplace with one plugin in it: **Keel Connect**.

```bash
claude plugin marketplace add keeldiscovery/keel-marketplace
claude plugin install keel@keel
```

Then say "keel connect" in Claude Code. You get a code and a URL, you approve the device in your
browser, and the Keel runtime on your machine is connected. Say "keel disconnect" to stop it again.

## What is in here

`.claude-plugin/marketplace.json` and a byte-identical `.github/plugin/marketplace.json` — the first is where Claude Code looks, the second where GitHub Copilot CLI looks (it reads the `.claude-plugin/` copy too), so one repository serves both hosts:

```bash
copilot plugin marketplace add keeldiscovery/keel-marketplace
copilot plugin install keel@keel
```

## Other hosts that read the same manifest

Two more hosts read a Claude-format `marketplace.json` as it is, so this repository serves them
unchanged. Neither is a measured host: the manifest is read and the skill loads, and we say no
more than that until each clears the four-part gate the landing page describes.

- **VS Code** (agent plugins): add `"chat.plugins.marketplaces": ["keeldiscovery/keel-marketplace"]`
  to your settings, then open the Extensions view, search `@agentPlugins`, and install **Keel
  Connect**.
- **JetBrains Junie CLI**: `/extensions marketplace add keeldiscovery/keel-marketplace`, then
  `/extensions install keel`.

And without any marketplace at all, Vercel's `skills` installer takes the plugin's skill straight
from the `release` branch, into whichever agents you have:

```bash
npx skills add https://github.com/keeldiscovery/keel-connect-skill/tree/release/skills/keel-connect
```

Nothing else. It names one plugin whose source is the
**`release` branch of [`keeldiscovery/keel-connect-skill`](https://github.com/keeldiscovery/keel-connect-skill)** —
that branch's root is the built plugin tree. One repository stays authoritative and browsable, and
there is no second copy of the skill to keep in step.

## This directory is generated

Do not hand-edit it. It is written by `make dist` in `keel-connect-skill`, from
`packaging/marketplace/marketplace.json.in`, with one substitution: the version. Edit it there.

Publishing a new version is `VERSION`, a tag, and a push in that repository; the marketplace entry
follows.

Licensed under Apache-2.0.
