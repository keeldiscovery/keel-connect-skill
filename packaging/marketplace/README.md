# keel-marketplace

A Claude Code plugin marketplace with one plugin in it: **Keel Connect**.

```bash
claude plugin marketplace add keeldiscovery/keel-marketplace
claude plugin install keel@keel
```

Then say "keel connect" in Claude Code. You get a code and a URL, you approve the device in your
browser, and the Keel runtime on your machine is connected. Say "keel disconnect" to stop it again.

## What is in here

`.claude-plugin/marketplace.json`, and nothing else. It names one plugin whose source is the
**`release` branch of [`keeldiscovery/keel-connect-skill`](https://github.com/keeldiscovery/keel-connect-skill)** —
that branch's root is the built plugin tree. One repository stays authoritative and browsable, and
there is no second copy of the skill to keep in step.

## This directory is generated

Do not hand-edit it. It is written by `make dist` in `keel-connect-skill`, from
`packaging/marketplace/marketplace.json.in`, with one substitution: the version. Edit it there.

Publishing a new version is `VERSION`, a tag, and a push in that repository; the marketplace entry
follows.

Licensed under Apache-2.0.
