# Feature Specification: One source, four trees, one build

**Feature Branch**: `004-skill-packaging`

**Created**: 2026-09-09

**Status**: Implemented

**Design of record**: keel-cloud `canon/designs/keel-skill-design.md` (2026-09-08). This spec is
**step 4** of its §13 implementation order and adds nothing that document does not decide. Every
requirement below cites the invariant id it comes from (§9), and so does the code.

**Input**: the design's §8, in its own words: *four hand-maintained copies is the failure this
design exists to prevent; a copy a build step makes and a test compares is not that failure.*

## Scope, stated first

**What lands here**: `VERSION`; `LICENSE`; `packaging/` -- the templates and hand-written words for
each packaging; `make dist`, writing `dist/{plugin,speckit,bare,copilot-repo}` plus
`dist/marketplace/` and `dist/speckit-catalog-entry.json`; `.gitignore` for `dist/`; and
`tests/test_dist.py` -- **L1, the gate**.

**Not building**: the GitHub repository `keeldiscovery/keel-marketplace`. The tree that goes in it
is generated at `dist/marketplace/`; creating the repository, pushing it, and creating the
`release` branch of this repository are the founder's, and are named in `README.md` rather than
automated. Not filing the Spec Kit submission issue (§8.4 steps 3-10) -- also the founder's. Not
building L2 (keel-e2e-eval's S-009, spec `013-skill-distribution`) or L3 (keel-cloud's
`KeelConnectSkillJourneyTest`), which are other repositories'. Not building a Copilot plugin
manifest, which the design defers until its shape has been read (decision 18, open question 3). Not
building CI's release automation: `make dist` is the thing CI would call, and it exists now.

**Depends on** spec `003-bundled-runtime` for a runtime to copy and a `RUNTIME_VERSION` to name it
with, and on spec `002-keel-disconnect` for the second script and the finished frontmatter -- L1
asserts things about both.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A founder installs the plugin and says it once (Priority: P1)

`claude plugin marketplace add keeldiscovery/keel-marketplace`, `claude plugin install keel@keel`,
"keel connect". Nothing else installed, nothing downloaded.

**Independent Test**: `make dist`, then the host's own validator against `dist/plugin` and
`dist/marketplace`, and the built tree carrying `SKILL.md`, `scripts/` and `keel_runtime/`.

**Acceptance Scenarios**:

1. **Given** a built `dist/plugin`, **When** `claude plugin validate --strict` runs against it,
   **Then** it passes -- and against `dist/marketplace` too.
2. **Given** the same tree, **Then** its `plugin.json` declares no `skills` path, no `hooks`, no
   `mcpServers`, no `dependencies` and no `userConfig` (D6): a plugin that behaved differently
   from a plain copy of the same skill would be a plugin nobody could reason about.

### User Story 2 - A team commits the skill into their repository (Priority: P1)

`dist/copilot-repo/.github/skills/keel-connect/` goes into a team's own repository. Reviewed like
code, the same for everyone on the next `git pull`, no installer and no network.

**Acceptance Scenarios**:

1. **Given** the built drop, **Then** it carries no manifest and no installer, because its whole
   point is that it needs neither.
2. **Given** the same drop, **Then** its `SKILL.md`, `scripts/` and `keel_runtime/` are
   byte-identical to the plugin's, the extension's and the bare tree's.

### User Story 3 - One machine, either agent, no marketplace (Priority: P2)

`./install.sh --host claude|copilot|agents [--project]`. A flag, not a fifth tree.

**Acceptance Scenarios**:

1. **Given** `dist/bare`, **When** `install.sh --host <h> --dry-run` runs for each host, **Then**
   it names the directory the design names and copies nothing.
2. **Given** an unknown host, **Then** it refuses rather than guessing.
3. **Given** any host, **Then** the installer edits no `PATH` and no shell profile (X-6).

### User Story 4 - A Spec Kit user adds the extension (Priority: P2)

`specify extension add keel`, two commands: `speckit.keel.connect` and the prose-only
`speckit.keel.brief`. 1.0.0 replaces 0.2.0 outright.

**Acceptance Scenarios**:

1. **Given** the built `extension.yml`, **Then** it carries `schema_version: "1.0"`, id `keel`,
   version `${VERSION}` substituted, `requires.speckit_version: ">=1.0.0,<2.0.0"`, exactly two
   correctly namespaced commands, and **no** `hooks`, `config` or `templates` (D6, decision 15).
2. **Given** the same, **Then** every path it names resolves inside the built tree.
3. **Given** `commands/brief.md`, **Then** it runs nothing, names no URL, and tells the agent the
   three readings -- evidence, opinion, source material.
4. **Given** `dist/speckit-catalog-entry.json`, **Then** it is generated from that manifest, agrees
   with it field by field, and sends no value the maintainers own.

### User Story 5 - A release, end to end (Priority: P2)

Edit `VERSION`, tag, push. One tag, three artifacts, one number.

**Acceptance Scenarios**:

1. **Given** any built tree or manifest, **Then** the version in it is `VERSION`'s (D7).
2. **Given** `dist/`, **Then** nothing in it is committed.

### Edge Cases

- **A hand edit in a built tree.** Caught by L1's byte comparison, in either direction: an edit to
  a copy, and an edit to the source that a stale build did not pick up.
- **A `keel_runtime/` that is not the one `RUNTIME_VERSION` names.** Compared against the sibling
  checkout when it is present and on that commit; skipped with a message when it is not, because
  this repository must stay buildable with no sibling at all.
- **A Windows runner with no `make`.** L1 skips itself with a message. What Windows is in the
  matrix to prove is that the *skill* runs there, not that a tarball can be built there.
- **A host CLI that is not installed.** The validator that exists is run; the one that does not is
  skipped **with a message**, never silently passed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** `VERSION` MUST exist and MUST be bare semver with no leading `v`.
- **FR-002** `make dist` MUST write four trees -- `dist/plugin`, `dist/speckit`, `dist/bare`,
  `dist/copilot-repo` -- from the one source in this repository.
- **FR-003** `make dist` MUST **copy**; the only generated bytes are the manifests, the version
  they carry, and the catalogue entry.
- **FR-004** All four trees MUST carry byte-identical `SKILL.md`, `scripts/` and `keel_runtime/`
  (D1, D2), and L1 MUST assert it.
- **FR-005** Every manifest MUST carry `VERSION` (D7), and none may declare a hook, an MCP server,
  an environment variable, a dependency or a default that changes what the script does (D6).
- **FR-006** `make dist` MUST also write `dist/marketplace/` -- the tree for the
  `keeldiscovery/keel-marketplace` repository -- naming one plugin sourced from this repository's
  `release` branch. **It MUST NOT create or push any repository.**
- **FR-007** `make dist` MUST write `dist/speckit-catalog-entry.json`, generated from the built
  `extension.yml`, **outside** every shipped tree.
- **FR-008** `packaging/` MUST hold the templates and every hand-written word: the plugin manifest
  and README, the extension manifest, its two command files, README, CHANGELOG and
  `tests/test-install.sh`, the bare installer, the Copilot drop's README, and the marketplace
  manifest and README.
- **FR-009** `install.sh` MUST accept `--host claude|copilot|agents`, `--project`, `--dest`,
  `--dry-run` and `--force`, MUST refuse an unknown host, and MUST edit no `PATH` and no shell
  profile (X-6).
- **FR-010** `tests/test_dist.py` MUST be L1 as §10.1 lists it, and MUST run `claude plugin
  validate --strict` when the `claude` CLI is present.
- **FR-011** `SKILL.md`'s frontmatter MUST parse with key set exactly `{name, description,
  license}`, under 1,024 characters with a `description` under 500, asserted by L1.
- **FR-012** L1 MUST assert D4's and D5's greps over `SKILL.md` and the scripts, that no reply
  hard-codes an address (X-5), that each half of the file tells the agent to name the
  `environment`, and that the Python clause is in *Running the check*.
- **FR-013** `dist/` MUST be gitignored.
- **FR-014** Both interpreters MUST be green.

### Non-functional / invariants carried

`D1`, `D2`, `D4`, `D5`, `D6`, `D7` from the design's §9 distribution table; `X-4`, `X-5`, `X-6`
from its skill table. `T-1` is honoured by construction: no tree is staged by hand and no test here
sets `KEEL_RUNTIME_PATH`.

## Key Entities

- **`VERSION` / `RUNTIME_VERSION`** -- the skill's own number, and which runtime it carries.
- **`packaging/`** -- templates and hand-written words. Nothing generated lives here.
- **`dist/`** -- four trees, one marketplace tree, one catalogue entry. Never committed.
- **L1** -- `tests/test_dist.py`. The gate.

## Success Criteria *(mandatory)*

- **SC-001** One skill: a hand edit in any tree is red.
- **SC-002** One runtime: every copy is the one `make runtime` placed.
- **SC-003** One version: every manifest agrees with `VERSION`.
- **SC-004** No manifest changes what the script does.
- **SC-005** The plugin and the marketplace pass the host's own validator, on `--strict`.
- **SC-006** The submission's catalogue entry cannot disagree with the manifest it was built from.
- **SC-007** The build is offline and needs no host CLI; where one is present, it is used.

## Findings

Two, both recorded rather than worked around, and both worth the founder's eye.

**F-1 -- `specify` has no `extension validate`, and the CLI here is 0.16.4.** Measured 2026-09-09.
`specify extension --help` lists `list`, `add`, `remove`, `search`, `info`, `update`, `enable`,
`disable`, `set-priority` and `catalog`, and nothing else -- there is no validate subcommand to
call, on this version. `specify extension add --from` on 0.16.4 takes a **URL only** (a local path
is rejected as an invalid URL). Serving the built tree as a zip over HTTP gets further: the
manifest is downloaded, read, and **its `requires` is honoured** -- *"Extension requires spec-kit
>=1.0.0,<2.0.0, but 0.16.4 is installed."* That is the design's `requires.speckit_version` working
exactly as intended, and it is the closest thing to a validation available here. **So L1 checks the
Spec Kit manifest structurally, against the fields the design's §8.4 lists**, and says so in the
test's own docstring rather than quietly implying a validator ran. A real install into a scratch
project on a 1.x CLI is `tests/test-install.sh --full` in the shipped tree, and acceptance A-13.

**F-2 -- `keel` 0.2.0 *is* in Spec Kit's community catalogue today.** The design's §8.4 and
decision 19 both say it "was never in the community catalogue, which is the only place `specify
extension update` resolves from", and use that to argue there is no install to carry forward even
in principle. `specify extension search keel` and `specify extension info keel`, run 2026-09-09,
return **`Keel Discovery (v0.2.0)`, source catalog `community`, category `process`, effect
`read-write`, 6 commands, 2 hooks, requires `>=0.15.0`, Downloads: 0, Stars: 0**. The "no
downloads" half of the argument holds; the "never catalogued" half does not. This does not change
decision 19 -- same id, same repository, 1.0.0 replaces 0.2.0 outright -- and step 10 already
describes exactly what happens (the workflow finds the id present and replaces the entry in place,
preserving `created_at`, `downloads` and `stars`). What it changes is the *first* submission's
framing: it is an **update to a catalogued extension**, not a first listing, and the design's
premise should be amended to say so.

## Assumptions

- The `release` branch of this repository, whose root is `dist/plugin/`, is created by the founder
  or by CI. Nothing here pushes a branch.
- `keeldiscovery/keel-marketplace` does not exist yet. `dist/marketplace/` is its contents.
- `keeldiscovery/spec-kit-keel` exists at 0.2.0 and is the repository 1.0.0 replaces in place.
