# Tasks: One source, four trees, one build

**Branch**: `004-skill-packaging` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Design of record**: keel-cloud `canon/designs/keel-skill-design.md` §13 step 4.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Foundational

- [X] T001 `VERSION` -> `1.0.0`, bare semver with no leading `v` (the catalogue validator's rule 2,
  and D7's single number). `RUNTIME_VERSION` is left exactly as `make runtime` stamped it.

- [X] T002 `LICENSE` -- Apache-2.0, the same file the 0.2.0 extension shipped, so the licence a
  founder receives does not change with the packaging.

- [X] T003 `.gitignore`: `/dist/`, rooted, with the comment saying why. Built, never committed.

## Phase 2: The templates and the words (US1-US4)

- [X] T004 [US1] `packaging/plugin/plugin.json.in`: name, displayName, version, description,
  author, homepage, repository, license, keywords -- and **no** `skills` path, `hooks`,
  `mcpServers`, `dependencies` or `userConfig` (D6, decision 15).

- [X] T005 [P] [US1] `packaging/plugin/README.md`: what it is, the two install lines, the one
  prerequisite, and what it deliberately is not.

- [X] T006 [P] [US1] `packaging/marketplace/{marketplace.json.in,README.md}`: one plugin, sourced
  `{source: github, repo: keeldiscovery/keel-connect-skill, ref: release}` (decision 14), and a
  README saying the directory is generated and where to edit it.

- [X] T007 [US4] `packaging/speckit/extension.yml.in`: the design's §8.4 manifest verbatim --
  `schema_version: "1.0"`, id `keel`, `${VERSION}`, `requires.speckit_version ">=1.0.0,<2.0.0"`,
  `tools: python3 >=3.9`, two commands, one script, five tags, no hooks and no config.

- [X] T008 [P] [US4] `packaging/speckit/commands/connect.md`: five lines of delegation naming the
  script's real relative path, plus the two things about the reply that are easy to get wrong.

- [X] T009 [P] [US4] `packaging/speckit/commands/brief.md`: the design's draft, in full, unchanged.
  Prose only -- no script, no URL, nothing fetched.

- [X] T010 [P] [US4] `packaging/speckit/{README.md,CHANGELOG.md}`: the design's drafted openings,
  carried through.

- [X] T011 [US4] `packaging/speckit/tests/test-install.sh`: what 0.2.0's became -- the manifest
  against the **built** tree, the five validator rules of §8.4 step 4 with the Python assertion at
  **3.9**, both scripts actually answering, and `--full` for the download-URL fetch and a real
  `specify` install. The static half L1 already owns is deliberately not duplicated.

- [X] T012 [US3] `packaging/bare/install.sh`: `--host claude|copilot|agents`, `--project`,
  `--dest`, `--dry-run`, `--force`; refuses an unknown host; edits no `PATH` and no shell profile
  (X-6); tells a founder about the 3.9 floor when their interpreter is below it or absent.

- [X] T013 [P] [US2] `packaging/copilot/repo/README.md`: the note for a team that commits the
  directory, and the personal install for anyone who would rather not.

## Phase 3: The build (US5)

- [X] T014 `make dist`: refuses without a `keel_runtime/` and without both version files; wipes
  `dist/`; writes the four trees, the marketplace tree and the catalogue entry. One `place_skill`
  macro copies the three things every tree shares, so there is one line to change if that set ever
  does; one `stamp` macro is the only transformation in the file.

- [X] T015 `packaging/catalog_entry.py`: reads the **built** manifest and writes
  `dist/speckit-catalog-entry.json`, so the submission and the manifest cannot disagree. Sends no
  value the maintainers own. A build tool -- it ships in no tree.

## Phase 4: L1, the gate

- [X] T016 `tests/test_dist.py::OneSkillTestCase`: `SKILL.md`, `scripts/` and `keel_runtime/`
  byte-identical across all four trees and to the source (D1, D2); no tree carrying Python outside
  those two directories; and the runtime compared against the sibling checkout when it is present
  and on the commit `RUNTIME_VERSION` names.

- [X] T017 [P] `OneVersionTestCase`: `VERSION` bare semver, and every manifest, the marketplace
  entry and the catalogue entry carrying it (D7).

- [X] T018 [P] `PluginManifestTestCase` and `MarketplaceTestCase`: the fields the design lists, the
  forbidden-key list for D6, no declared `skills` path, and the marketplace naming one plugin from
  the `release` branch.

- [X] T019 [P] `HostCliValidationTestCase`: `claude plugin validate --strict` against the built
  plugin and the built marketplace, skipped **with a message** when the CLI is absent.

- [X] T020 [P] `SpecKitManifestTestCase` and `CatalogueEntryTestCase`: the manifest's shape, its
  two namespaced commands, every path resolving in the built tree, D6's forbidden keys, the connect
  command naming the real script path, the brief command being prose only -- and the catalogue
  entry agreeing with the manifest field by field. The docstring records what `specify` 0.16.4 can
  and cannot do here (spec.md F-1), rather than implying a validator ran.

- [X] T021 [P] `BareInstallerTestCase` and `CopilotRepoDropTestCase`: every host's `--dry-run`
  destination, an unknown host refused, X-6 asserted over the installer's own source, and the drop
  carrying no manifest and no installer.

- [X] T022 [P] `SkillFileTestCase`: the frontmatter key set **exactly** three, both lengths, the
  description trigger-first and naming both jobs, the name unchanged, each half of the file telling
  the agent to name the `environment`, no hard-coded address (X-5), D4's and D5's greps, the Python
  clause in *Running the check*, and X-4.

## Phase 5: The words, and the floor

- [X] T023 `README.md` and `AGENTS.md` brought level: `make dist`, the four trees, what is the
  founder's to do by hand, and the two findings.

- [X] T024 The floor, run: the whole suite green on `/usr/bin/python3` (3.9.6) and on the newest
  interpreter present (3.12.5).

## What is deliberately not here

- **Creating `keeldiscovery/keel-marketplace`,** pushing it, or cutting this repository's `release`
  branch. The tree is generated; the acts with consequences outside this machine are the founder's.
- **Filing the Spec Kit submission issue** (§8.4 steps 3-10), and its ten-step plan.
- **L2 and L3.** keel-e2e-eval's S-009 (spec `013-skill-distribution`) and keel-cloud's
  `KeelConnectSkillJourneyTest`.
- **A Copilot plugin manifest** -- deferred until its shape has been read (decision 18).
- **CI release automation.** `make dist` is what it would call, and it exists now.

## Discovered

- **The marketplace tree serves GitHub Copilot CLI too, at no extra manifest.** Copilot CLI's
  canonical marketplace location is `.github/plugin/marketplace.json`; it also reads the
  `.claude-plugin/` copy at the same host's marketplace path, and `github/copilot-plugins` itself
  ships both files, byte-identical, in the one repository. `make dist` now writes
  `dist/marketplace/.github/plugin/marketplace.json` as a copy of the stamped
  `.claude-plugin/marketplace.json` it already wrote -- not a second generation, so the two cannot
  drift apart -- and `tests/test_dist.py::MarketplaceTestCase::test_the_github_copilot_location_is_byte_identical`
  is the L1 assertion that they are exactly the same bytes. `packaging/marketplace/README.md`
  carries the two Copilot install lines (`copilot plugin marketplace add
  keeldiscovery/keel-marketplace`, `copilot plugin install keel@keel`) alongside the two Claude
  Code ones it already had.
- **This makes `dist/copilot-repo` redundant for plugin distribution, not obsolete.** Once
  `keeldiscovery/keel-marketplace` carries a Copilot-readable manifest, `copilot plugin install
  keel@keel` is the shorter path to the same bytes `dist/copilot-repo` (the `.github/skills/`
  drop, §8.3) also delivers -- a marketplace install needs no directory committed into a team's own
  repository and updates with `copilot plugin update` rather than a `git pull` a maintainer has to
  remember to make. `dist/copilot-repo` is kept anyway, for the reason §8.3 already gives it: a
  team that wants the skill committed and reviewed like code, in a repository no marketplace or
  network reaches, still has no other packaging that serves that.
- **`keeldiscovery/keel-marketplace` was created and pushed, by hand, outside this repository's own
  build** (as `What is deliberately not here` above says it would be): one commit for the tree
  `make dist` writes, a second adding the Copilot location once its shape was read. `make dist`
  was then brought to match those bytes exactly, rather than the other way around.
- **This repository's `release` branch was cut** (§8.2, decision 14): an orphan branch whose root
  is `dist/plugin/` built from this exact `master` commit, via a new `make release` target
  (refuses on a dirty tree; force-updates `release` from the current build), pushed to
  `origin/release`. See the commit message on that branch for the source commit and
  `RUNTIME_VERSION` it names.

## Acceptance evidence: installable end to end (2026-09-09, this Mac)

Measured after `master` 2b30230 was pushed and `make release` cut `origin/release` at 3a51310
(root; `dist/plugin/` from that commit, `RUNTIME_VERSION 0.1.0+a0756b6`). Both marketplaces were
private-or-public as GitHub had them at the time; no visibility change was made for this test.

**Claude Code (2.1.263).**
```
$ claude plugin marketplace add keeldiscovery/keel-marketplace
Adding marketplace…Cloning via SSH: git@github.com:keeldiscovery/keel-marketplace.git
✔ Successfully added marketplace: keel (declared in user settings)
$ claude plugin install keel@keel
Installing plugin "keel@keel"...✔ Successfully installed plugin: keel@keel (scope: user)
$ claude plugin list
Installed plugins:
  ❯ keel@keel
    Version: 1.0.0
    Scope: user
    Status: ✔ enabled
```
`SKILL.md` landed at `~/.claude/plugins/cache/keel/keel/1.0.0/skills/keel-connect/SKILL.md`. The
add succeeded through the founder's own SSH git credentials (`git@github.com:...`), so this proves
nothing about whether the repository is public to a stranger.

**GitHub Copilot CLI (1.0.83).**
```
$ copilot plugin marketplace add keeldiscovery/keel-marketplace
Marketplace "keel" added successfully.
$ copilot plugin install keel@keel
Plugin "keel" installed successfully. Installed 1 skill.
$ copilot plugin list
Installed plugins:
  • keel@keel (v1.0.0)
$ copilot skill list
Project skills:
  keel-connect - Use when the user says or means "keel connect" ...
Builtin skills:
  customize-cloud-agent - ...
  github-pr-media - ...
```
`keel-connect` is listed separately from Copilot's two `Builtin skills` under its own "Project
skills" heading -- Copilot's label for a skill a plugin provided, distinct from a skill it ships
with. It landed at `~/.copilot/installed-plugins/keel/keel/skills/keel-connect/`. **Contrary to
the concern this task was framed with, Copilot's plain clone did not fail on auth** -- it added
and installed cleanly on the same run, same machine, same repository visibility.

**Cleanup, both hosts, confirmed by each CLI's own listing going back to empty:**
```
$ copilot plugin uninstall keel@keel && copilot plugin marketplace remove keel
$ claude plugin uninstall keel@keel && claude plugin marketplace remove keel
```
`claude plugin list` / `claude plugin marketplace list` and `copilot plugin list` /
`copilot plugin marketplace list` all report nothing installed and only each host's stock
marketplace afterward. Left behind, and not cleaned further because neither CLI's own state
considers it installed: `~/.claude/plugins/cache/keel/` and
`~/.copilot/Library/Caches/copilot/marketplaces/keeldiscovery-*` -- ordinary download caches, the
same shape either tool leaves after uninstalling anything.
