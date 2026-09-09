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
