"""L1 -- the packaging tests. **This is the gate** (keel-cloud `canon/designs/keel-skill-design.md`
§10.1).

`make dist` builds four trees plus the marketplace from one source. Everything below asks the one
question that matters about a build like that: **did anything drift?** One skill (D1), one runtime
(D2), one version (D7), no behaviour in a manifest (D6), no ecosystem in the skill (D4), no host in
a reply (D5).

Fast, offline, no host CLI required -- and where a host CLI *is* present, it is used: `claude
plugin validate --strict` runs against the built plugin and the built marketplace when the `claude`
command is on `PATH`, and is skipped with a message when it is not.

Spec Kit's own manifest is checked **structurally**, against the fields the design lists, because
there is no `specify extension validate` subcommand to check it with -- see
`SpecKitManifestTestCase` for what was measured, when, and against which CLI version.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST = REPO_ROOT / "dist"
SOURCE_SKILL = REPO_ROOT / "SKILL.md"
SOURCE_SCRIPTS = REPO_ROOT / "scripts"
SOURCE_RUNTIME = REPO_ROOT / "keel_runtime"
VERSION = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()

# Where the one skill lands in each tree. The **four packagings** of §8, and the assertion that
# they are one skill is the assertion that these four directories are byte-identical.
TREES = {
    "plugin": DIST / "plugin" / "skills" / "keel-connect",
    "speckit": DIST / "speckit",
    "bare": DIST / "bare" / "keel-connect",
    "copilot-repo": DIST / "copilot-repo" / ".github" / "skills" / "keel-connect",
}

def _find_bash():
    """A real `bash`, not `%SystemRoot%\\System32\\bash.exe` -- the WSL launcher stub GitHub's
    `windows-latest` runners put on `PATH` ahead of Git for Windows' own `bash.exe`. With no WSL
    distribution installed (true of every runner in this repository's matrix) that stub exits
    non-zero before running anything, which every caller of `_find_bash` here would otherwise read
    as this repository's script failing to parse. Git for Windows' bash is a real POSIX `bash` --
    the one `install.sh`, `test-install.sh` and their tests need -- so it is checked for by its own
    known install locations first; `shutil.which("bash")` (which will find the stub) is the
    fallback everywhere else, including on a Windows machine with no Git for Windows at all, so a
    caller still gets a clear "no bash here" skip rather than a wrong binary silently substituted.
    """
    if os.name == "nt":
        seen = set()
        for env_var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
            base = os.environ.get(env_var)
            if not base or base in seen:
                continue
            seen.add(base)
            for tail in (r"Git\bin\bash.exe", r"Git\usr\bin\bash.exe"):
                candidate = os.path.join(base, tail)
                if os.path.isfile(candidate):
                    return candidate
    return shutil.which("bash")


def _find_pwsh():
    """PowerShell 7+ -- preinstalled on every GitHub-hosted runner in this repository's matrix
    (`windows-latest`, `macos-latest`, `ubuntu-latest`), so this needs no Windows-only fallback the
    way `_find_bash` does; a developer machine with neither `pwsh` nor Windows PowerShell simply
    skips, the same way a machine with no `bash` does."""
    return shutil.which("pwsh")


_BUILD_ERROR = None


def setUpModule():
    """One `make dist`, for the whole module. The tests read what it wrote; none of them builds."""
    global _BUILD_ERROR
    if not (SOURCE_RUNTIME / "__main__.py").is_file():
        _BUILD_ERROR = "no keel_runtime/ here -- run `make runtime` first"
        return
    if shutil.which("make") is None:
        # The gate runs on every commit on the Linux and macOS rows, which is where a release is
        # built. A Windows row with no `make` skips it rather than failing: what Windows is in the
        # matrix to prove is that the *skill* runs there, not that a tarball can be built there.
        _BUILD_ERROR = "no `make` on PATH -- the packaging gate needs one to build dist/"
        return
    completed = subprocess.run(["make", "dist"], cwd=str(REPO_ROOT),
                               capture_output=True, text=True, timeout=300)
    if completed.returncode != 0:
        _BUILD_ERROR = "make dist failed:\n%s\n%s" % (completed.stdout, completed.stderr)


class DistTestCase(unittest.TestCase):
    def setUp(self):
        if _BUILD_ERROR:
            self.skipTest(_BUILD_ERROR)

    # ------------------------------------------------------------------------------------ helpers

    @staticmethod
    def files_under(directory):
        """Every file under a directory, as {relative path: bytes}, caches excluded."""
        found = {}
        for path in sorted(Path(directory).rglob("*")):
            if path.is_dir() or "__pycache__" in path.parts or path.suffix in (".pyc", ".pyo"):
                continue
            found[str(path.relative_to(directory))] = path.read_bytes()
        return found

    def frontmatter(self, skill_md_text):
        """The raw frontmatter block of a SKILL.md, and its keys. Parsed the way a host's own
        matcher would have to: the block between the first two `---` lines, one `key: value` per
        line, no nesting -- which is itself part of what is being asserted."""
        self.assertTrue(skill_md_text.startswith("---\n"), "SKILL.md must open with frontmatter")
        block = skill_md_text.split("---\n", 2)[1]
        keys = re.findall(r"^([A-Za-z][A-Za-z0-9_-]*):", block, re.M)
        return block, keys


# ================================================================== D1, D2 -- one skill, one runtime


class OneSkillTestCase(DistTestCase):
    """D1: `SKILL.md` and `scripts/` exist in exactly one place in one repository; a packaging
    copies and never edits. D2: every `keel_runtime/` is a copy of one source.

    Four hand-maintained copies is the failure this design exists to prevent, and this is the test
    that would catch the first hand edit -- in any of the four trees, in either direction.
    """

    def test_all_four_trees_exist(self):
        for name, root in TREES.items():
            with self.subTest(tree=name):
                self.assertTrue(root.is_dir(), "%s was not built at %s" % (name, root))

    def test_skill_md_is_byte_identical_everywhere(self):
        source = SOURCE_SKILL.read_bytes()
        for name, root in TREES.items():
            with self.subTest(tree=name):
                self.assertEqual((root / "SKILL.md").read_bytes(), source,
                                 "D1: %s's SKILL.md is not the one source copy" % name)

    def test_the_version_file_travels_with_every_tree(self):
        """Spec `005-upgrade-in-place`: the connect check reads the skill's own `VERSION` at the
        tree's root to know whether it is newer than the runtime already running. So the file is
        in `SKILL_FILES` and every packaging carries it, byte for byte (D7: one number)."""
        source = (REPO_ROOT / "VERSION").read_bytes()
        for name, root in TREES.items():
            with self.subTest(tree=name):
                self.assertEqual((root / "VERSION").read_bytes(), source,
                                 "D7: %s's VERSION is not the one number" % name)

    def test_scripts_are_byte_identical_everywhere(self):
        source = self.files_under(SOURCE_SCRIPTS)
        self.assertIn("keel_connect_check.py", source)
        self.assertIn("keel_disconnect.py", source)
        self.assertIn("_runtime_location.py", source)
        for name, root in TREES.items():
            with self.subTest(tree=name):
                self.assertEqual(self.files_under(root / "scripts"), source,
                                 "D1: %s's scripts/ is not the one source copy" % name)

    def test_the_runtime_package_is_byte_identical_everywhere(self):
        source = self.files_under(SOURCE_RUNTIME)
        self.assertIn("__main__.py", source)
        for name, root in TREES.items():
            with self.subTest(tree=name):
                self.assertEqual(self.files_under(root / "keel_runtime"), source,
                                 "D2: %s's keel_runtime/ is not the one copied package" % name)

    def test_no_tree_carries_a_second_copy_of_anything(self):
        """A tree may add its own words -- a README, a manifest, a command file -- but never a
        second copy of a script or of the runtime under another name."""
        for name, root in TREES.items():
            with self.subTest(tree=name):
                stray = [rel for rel in self.files_under(root)
                         if rel.endswith(".py")
                         and not rel.startswith("scripts" + os.sep)
                         and not rel.startswith("keel_runtime" + os.sep)]
                self.assertEqual(stray, [], "%s carries Python outside scripts/ and keel_runtime/"
                                 % name)

    def test_the_runtime_is_the_one_runtime_version_names(self):
        """D2's other half: `RUNTIME_VERSION` names a commit of keel-runtime, and the package here
        is that commit's. Compared against the sibling checkout when it is present and on that
        commit; otherwise the version string is checked and the byte comparison is skipped, since
        this repository must stay buildable and testable with no sibling at all."""
        recorded = (REPO_ROOT / "RUNTIME_VERSION").read_text(encoding="utf-8").strip()
        self.assertTrue(recorded, "`make runtime` stamps which runtime this skill carries")
        self.assertIn(recorded.lstrip("v").split("+")[0],
                      (SOURCE_RUNTIME / "__init__.py").read_text(encoding="utf-8"))

        sibling = REPO_ROOT.parent / "keel-runtime"
        if not (sibling / "keel_runtime" / "__main__.py").is_file():
            self.skipTest("no ../keel-runtime checkout here to compare against")
        head = subprocess.run(["git", "-C", str(sibling), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True)
        if head.returncode != 0 or "+" not in recorded:
            self.skipTest("RUNTIME_VERSION names a tag, or the sibling is not a git checkout")
        if head.stdout.strip() != recorded.split("+", 1)[1]:
            self.skipTest("../keel-runtime is at %s, not the %s RUNTIME_VERSION names"
                          % (head.stdout.strip(), recorded.split("+", 1)[1]))
        self.assertEqual(self.files_under(SOURCE_RUNTIME),
                         self.files_under(sibling / "keel_runtime"),
                         "D2: the copied package is not byte-identical to its one source")


# ============================================================================ D7 -- one version


class OneVersionTestCase(DistTestCase):
    """Every packaging of a release carries the same `VERSION`."""

    def test_version_is_bare_semver(self):
        self.assertRegex(VERSION, r"^\d+\.\d+\.\d+$",
                         "bare semver with no leading v -- the catalogue validator's rule 2")

    def test_the_plugin_manifest_carries_it(self):
        manifest = json.loads(
            (DIST / "plugin" / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], VERSION)

    def test_the_extension_manifest_carries_it(self):
        text = (DIST / "speckit" / "extension.yml").read_text(encoding="utf-8")
        self.assertIn("version: %s" % VERSION, text)
        self.assertNotIn("${VERSION}", text, "the template was substituted, not copied")

    def test_the_marketplace_entry_carries_it(self):
        manifest = json.loads(
            (DIST / "marketplace" / ".claude-plugin" / "marketplace.json").read_text("utf-8"))
        self.assertEqual(manifest["plugins"][0]["version"], VERSION)

    def test_the_catalogue_entry_carries_it(self):
        entry = json.loads((DIST / "speckit-catalog-entry.json").read_text(encoding="utf-8"))
        self.assertEqual(entry["version"], VERSION)
        self.assertIn("/v%s.zip" % VERSION, entry["download_url"])


# ================================================================= the Claude Code plugin (§8.2)


class PluginManifestTestCase(DistTestCase):
    def manifest(self):
        return json.loads(
            (DIST / "plugin" / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))

    def test_it_parses_and_carries_what_the_design_lists(self):
        manifest = self.manifest()
        for key in ("name", "displayName", "version", "description", "author", "homepage",
                    "repository", "license", "keywords"):
            self.assertIn(key, manifest)
        self.assertEqual(manifest["name"], "keel")
        self.assertEqual(manifest["license"], "Apache-2.0")
        self.assertIsInstance(manifest["author"], dict)

    def test_no_behaviour_in_a_manifest(self):
        """D6: a manifest may declare a name, a version, a path and a description -- never a hook,
        an environment variable, an MCP server, or a default that changes what the script does.
        Each of these is a way to make the plugin behave differently from a bare drop."""
        manifest = self.manifest()
        for forbidden in ("hooks", "mcpServers", "dependencies", "userConfig", "env",
                          "lspServers", "experimental", "outputStyles"):
            self.assertNotIn(forbidden, manifest,
                             "D6: `%s` would make this plugin behave unlike a plain copy of the "
                             "same skill" % forbidden)

    def test_it_declares_no_skills_path(self):
        """`skills/` at the plugin root is the default and is auto-discovered. Declaring it would
        be a second statement of one fact."""
        self.assertNotIn("skills", self.manifest())
        self.assertTrue((DIST / "plugin" / "skills" / "keel-connect" / "SKILL.md").is_file())

    def test_the_tree_carries_its_own_words_and_its_licence(self):
        self.assertTrue((DIST / "plugin" / "README.md").is_file())
        self.assertTrue((DIST / "plugin" / "LICENSE").is_file())


class MarketplaceTestCase(DistTestCase):
    """`keeldiscovery/keel-marketplace`: one manifest naming one plugin, whose source is the
    `release` branch of this repository (decision 14). The GitHub repository itself is the
    founder's to create; this builds the tree that goes in it."""

    def manifest(self):
        return json.loads(
            (DIST / "marketplace" / ".claude-plugin" / "marketplace.json").read_text("utf-8"))

    def test_it_names_one_plugin_from_the_release_branch(self):
        manifest = self.manifest()
        self.assertEqual(len(manifest["plugins"]), 1)
        source = manifest["plugins"][0]["source"]
        self.assertEqual(source["source"], "github")
        self.assertEqual(source["repo"], "keeldiscovery/keel-connect-skill")
        self.assertEqual(source["ref"], "release",
                         "the plugin is a `release` branch of this repository, so one repository "
                         "stays authoritative and browsable")

    def test_it_has_an_owner_and_a_name(self):
        manifest = self.manifest()
        self.assertEqual(manifest["name"], "keel")
        self.assertIn("name", manifest["owner"])

    def test_the_github_copilot_location_is_byte_identical(self):
        """GitHub Copilot CLI's canonical marketplace location is `.github/plugin/`; it also reads
        the `.claude-plugin/` copy, and `github/copilot-plugins` ships both. So this tree carries
        both, and they must be the same bytes -- one manifest, two places a host looks for it,
        never two manifests that could drift apart."""
        claude_plugin = (DIST / "marketplace" / ".claude-plugin" / "marketplace.json").read_bytes()
        github_plugin = (DIST / "marketplace" / ".github" / "plugin" / "marketplace.json").read_bytes()
        self.assertEqual(claude_plugin, github_plugin,
                         ".claude-plugin/marketplace.json and .github/plugin/marketplace.json "
                         "must be byte-identical")


class HostCliValidationTestCase(DistTestCase):
    """Where the host's own validator exists, it is the one that decides. Skipped, with a message,
    where it does not -- never silently passed."""

    def validate(self, path):
        if shutil.which("claude") is None:
            self.skipTest("no `claude` on PATH -- the host's own validator was not run here")
        completed = subprocess.run(["claude", "plugin", "validate", str(path), "--strict"],
                                   capture_output=True, text=True, timeout=120)
        self.assertEqual(completed.returncode, 0,
                         "claude plugin validate --strict:\n%s\n%s"
                         % (completed.stdout, completed.stderr))

    def test_the_plugin_validates(self):
        self.validate(DIST / "plugin")

    def test_the_marketplace_validates(self):
        self.validate(DIST / "marketplace")


# ===================================================================== the Spec Kit extension (§8.4)


class SpecKitManifestTestCase(DistTestCase):
    """**Structural, not validated by the CLI, and here is exactly why.**

    Measured 2026-09-09 on the machine this was written on: `specify` is installed at **0.16.4**,
    and it has **no `extension validate` subcommand** -- `specify extension --help` lists `list`,
    `add`, `remove`, `search`, `info`, `update`, `enable`, `disable`, `set-priority`, `catalog`,
    and nothing else. `specify extension add --from` on that version takes a URL only (a local
    path is rejected as an invalid URL), and installing the built tree from a URL reaches the
    compatibility gate and stops there: *"Extension requires spec-kit >=1.0.0,<2.0.0, but 0.16.4
    is installed."*

    That is the manifest being read and its `requires` being honoured, which is worth something --
    but it is not a validation, and this test does not pretend it is one. What is asserted below is
    every field the design's §8.4 manifest lists, in the shape it lists it. A real
    `specify extension add` into a scratch project on a 1.x CLI is `tests/test-install.sh --full`
    in the shipped tree, and acceptance A-13, and neither is this test.
    """

    def manifest_text(self):
        return (DIST / "speckit" / "extension.yml").read_text(encoding="utf-8")

    def test_the_manifest_shape(self):
        text = self.manifest_text()
        self.assertIn('schema_version: "1.0"', text)
        self.assertIn("id: keel", text)
        self.assertIn("name: Keel Connect", text)
        self.assertIn("author: Keel Discovery", text)
        self.assertIn("license: Apache-2.0", text)
        self.assertIn('speckit_version: ">=1.0.0,<2.0.0"', text)
        self.assertIn("repository: https://github.com/keeldiscovery/spec-kit-keel", text)

    def test_the_id_is_lowercase_with_hyphens(self):
        self.assertRegex("keel", r"^[a-z][a-z0-9-]*$")

    def test_the_description_is_under_two_hundred_characters(self):
        description = re.search(r"^  description: (.+)$", self.manifest_text(), re.M).group(1)
        self.assertLess(len(description), 200,
                        "the submission form and the manifest both cap this at 200")

    def test_two_commands_correctly_namespaced(self):
        names = re.findall(r"name: (speckit\.[a-z0-9.-]+)", self.manifest_text())
        self.assertEqual(names, ["speckit.keel.connect", "speckit.keel.brief"])
        for name in names:
            self.assertRegex(name, r"^speckit\.keel\.[a-z0-9-]+$",
                             "the namespace must equal extension.id")

    def test_every_path_the_manifest_names_resolves_in_the_built_tree(self):
        for rel in re.findall(r"file: ([^,}\s]+)", self.manifest_text()):
            with self.subTest(path=rel):
                self.assertTrue((DIST / "speckit" / rel).is_file(),
                                "a manifest that names a file it does not ship cannot install")

    def test_no_behaviour_in_a_manifest(self):
        """D6, and decision 15's "no hooks, in either ecosystem"."""
        text = self.manifest_text()
        for forbidden in ("hooks:", "config:", "templates:", "env:"):
            self.assertNotRegex(text, r"(?m)^%s" % re.escape(forbidden),
                                "D6: `%s` is behaviour, and a manifest may not carry it"
                                % forbidden)

    def test_the_connect_command_names_the_script_s_real_relative_path(self):
        """The one thing in a command file that can be wrong in a way nobody notices until a
        founder runs it."""
        text = (DIST / "speckit" / "commands" / "connect.md").read_text(encoding="utf-8")
        match = re.search(r"python3 (\S*scripts/keel_connect_check\.py)", text)
        self.assertIsNotNone(match, "connect.md must name the script it delegates to")
        named = match.group(1)
        self.assertTrue(named.endswith("scripts/keel_connect_check.py"))
        self.assertTrue((DIST / "speckit" / "scripts" / "keel_connect_check.py").is_file())

    def test_the_brief_command_is_prose_only(self):
        """It fetches nothing and holds no token: no script, no URL, no command to run."""
        text = (DIST / "speckit" / "commands" / "brief.md").read_text(encoding="utf-8")
        self.assertNotIn("```bash", text)
        self.assertNotIn("http://", text)
        self.assertNotIn("https://", text)
        self.assertIn("Download the brief", text)
        for reading in ("evidence", "opinion", "source material"):
            self.assertIn(reading, text)

    def test_the_shipped_tree_carries_what_a_submission_reads(self):
        for name in ("extension.yml", "README.md", "LICENSE", "CHANGELOG.md", "SKILL.md"):
            with self.subTest(file=name):
                self.assertTrue((DIST / "speckit" / name).is_file())
        script = DIST / "speckit" / "tests" / "test-install.sh"
        self.assertTrue(script.is_file())
        if os.name == "posix":
            self.assertTrue(os.access(str(script), os.X_OK), "test-install.sh must be executable")
        bash = _find_bash()
        if bash is not None:
            parsed = subprocess.run([bash, "-n", str(script)], capture_output=True, text=True)
            self.assertEqual(parsed.returncode, 0, parsed.stderr)


class CatalogueEntryTestCase(DistTestCase):
    """The entry the founder pastes into the submission issue, generated from the built manifest so
    the two cannot disagree (§8.4 step 6)."""

    def entry(self):
        return json.loads((DIST / "speckit-catalog-entry.json").read_text(encoding="utf-8"))

    def test_it_agrees_with_the_manifest(self):
        entry = self.entry()
        text = (DIST / "speckit" / "extension.yml").read_text(encoding="utf-8")
        self.assertEqual(entry["id"], "keel")
        self.assertIn("name: %s" % entry["name"], text)
        self.assertIn("description: %s" % entry["description"], text)
        self.assertIn("author: %s" % entry["author"], text)
        self.assertIn('speckit_version: "%s"' % entry["requires"]["speckit_version"], text)

    def test_the_fields_the_submission_form_requires(self):
        entry = self.entry()
        for key in ("id", "name", "description", "author", "version", "download_url",
                    "repository", "documentation", "changelog", "license", "category",
                    "effect", "requires", "provides", "tags"):
            self.assertIn(key, entry)
        self.assertEqual(entry["category"], "integration")
        self.assertEqual(entry["effect"], "read-only",
                         "neither command writes anything itself (X-6)")
        self.assertEqual(entry["provides"], {"commands": 2, "hooks": 0})
        self.assertTrue(2 <= len(entry["tags"]) <= 5, "the form asks for two to five tags")
        self.assertLess(len(entry["description"]), 200)

    def test_it_sends_no_value_the_maintainers_own(self):
        entry = self.entry()
        for theirs in ("verified", "downloads", "stars", "created_at", "updated_at"):
            self.assertNotIn(theirs, entry,
                             "step 6: do not send values for the maintainers' and the system's "
                             "own fields")

    def test_the_download_url_is_an_accepted_shape(self):
        self.assertRegex(
            self.entry()["download_url"],
            r"^https://github\.com/[^/]+/[^/]+/(archive/refs/tags/.+\.zip"
            r"|releases/download/[^/]+/.+\.zip)$")

    def test_it_is_outside_every_shipped_tree(self):
        """"Outside the tree; never shipped" -- it is the founder's paste buffer, not a file
        anybody installs."""
        for name, root in TREES.items():
            with self.subTest(tree=name):
                self.assertFalse((root / "speckit-catalog-entry.json").exists())


# ================================================================================ bare, and Copilot


class _BareInstallerBehaviorMixin:
    """`bare/install.{sh,ps1} --host claude|copilot|agents` -- the personal install as a flag, not
    a fifth tree (decision 13). One source behaviour, tested through whichever of the two shells
    this machine can actually run: `install.sh` is POSIX and needs `bash`; Windows has no `sh`, so
    it gets `install.ps1` instead (added 2026-09-09, keel-runtime acceptance run 34344993957's
    Windows job). Every concrete subclass below names its script, its interpreter, and how to spell
    the same four flags in that shell; `setUp` runs a subclass only on the OS its script targets,
    and skips it (never fails it) everywhere else or where the interpreter is missing -- exactly
    one of the two concrete subclasses reaches its tests' bodies on any given machine.
    """

    SCRIPT_NAME = None    # set by subclass: "install.sh" or "install.ps1"
    RUNS_ON_NT = None     # set by subclass: True for install.ps1, False for install.sh
    # Windows path separators here on purpose when RUNS_ON_NT: os.path.join already gives the
    # right one for the OS this subclass only ever runs on.
    FORBIDDEN_IN_SOURCE = ()

    def find_interpreter(self):
        raise NotImplementedError

    def argv_for(self, host=None, project=False, dry_run=False, force=False):
        """The interpreter-prefixed argv for one run, in this shell's own flag spelling."""
        raise NotImplementedError

    def installer(self):
        return DIST / "bare" / self.SCRIPT_NAME

    def setUp(self):
        super().setUp()
        if (os.name == "nt") != self.RUNS_ON_NT:
            self.skipTest("%s targets %s; not this machine" % (
                self.SCRIPT_NAME, "Windows" if self.RUNS_ON_NT else "POSIX"))
        self.interpreter = self.find_interpreter()
        if self.interpreter is None:
            self.skipTest("no interpreter here to run %s with" % self.SCRIPT_NAME)

    def test_the_skill_sits_beside_it(self):
        self.assertTrue((DIST / "bare" / "keel-connect" / "SKILL.md").is_file())

    def test_each_host_resolves_to_the_directory_the_design_names(self):
        expected = {
            ("claude", False): os.path.join("$HOME", ".claude", "skills", "keel-connect"),
            ("claude", True): os.path.join(".claude", "skills", "keel-connect"),
            ("copilot", False): os.path.join("$HOME", ".copilot", "skills", "keel-connect"),
            ("copilot", True): os.path.join(".github", "skills", "keel-connect"),
            ("agents", False): os.path.join("$HOME", ".agents", "skills", "keel-connect"),
        }
        for (host, project), tail in expected.items():
            with self.subTest(host=host, project=project):
                argv = self.argv_for(host=host, project=project, dry_run=True)
                completed = subprocess.run(argv, capture_output=True, text=True,
                                           cwd=str(DIST), timeout=60)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertIn(tail.replace("$HOME", os.path.expanduser("~")), completed.stdout)
                self.assertIn("nothing copied", completed.stdout,
                              "--dry-run/-DryRun must copy nothing")

    def test_an_unknown_host_is_refused_rather_than_guessed(self):
        argv = self.argv_for(host="emacs", dry_run=True)
        completed = subprocess.run(argv, capture_output=True, text=True, cwd=str(DIST), timeout=60)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("unknown host", completed.stderr)

    def test_it_really_copies_and_edits_nothing_outside_the_destination(self):
        """X-6: no `PATH` edit, no shell-profile edit, ever."""
        source = self.installer().read_text(encoding="utf-8")
        for forbidden in self.FORBIDDEN_IN_SOURCE:
            self.assertNotIn(forbidden, source)


class BareInstallerTestCase(_BareInstallerBehaviorMixin, DistTestCase):
    """The POSIX shell: `install.sh`, run with `bash`."""

    SCRIPT_NAME = "install.sh"
    RUNS_ON_NT = False
    FORBIDDEN_IN_SOURCE = (".bashrc", ".zshrc", ".profile", "export PATH", "/etc/")

    def find_interpreter(self):
        return _find_bash()

    def argv_for(self, host=None, project=False, dry_run=False, force=False):
        argv = [self.interpreter, str(self.installer())]
        if host is not None:
            argv += ["--host", host]
        if project:
            argv.append("--project")
        if dry_run:
            argv.append("--dry-run")
        if force:
            argv.append("--force")
        return argv

    def test_it_is_executable_and_parses(self):
        if os.name == "posix":
            self.assertTrue(os.access(str(self.installer()), os.X_OK))
        parsed = subprocess.run([self.interpreter, "-n", str(self.installer())],
                                capture_output=True, text=True)
        self.assertEqual(parsed.returncode, 0, parsed.stderr)


class BareInstallerWindowsTestCase(_BareInstallerBehaviorMixin, DistTestCase):
    """Windows has no `sh`: `install.ps1`, run with `pwsh`. Same behaviour as `install.sh`, in
    PowerShell's own flag spelling (`-HostName` rather than `-Host` -- PowerShell's automatic
    `$Host` variable makes `-Host` an unusable parameter name; see the script's own docstring)."""

    SCRIPT_NAME = "install.ps1"
    RUNS_ON_NT = True
    FORBIDDEN_IN_SOURCE = ("$PROFILE", "SetEnvironmentVariable", "$env:Path =", "$env:PATH =")

    def find_interpreter(self):
        return _find_pwsh()

    def argv_for(self, host=None, project=False, dry_run=False, force=False):
        argv = [self.interpreter, "-NoProfile", "-File", str(self.installer())]
        if host is not None:
            argv += ["-HostName", host]
        if project:
            argv.append("-Project")
        if dry_run:
            argv.append("-DryRun")
        if force:
            argv.append("-Force")
        return argv

    def test_it_parses(self):
        check = (
            "$errs = $null; "
            "$null = [System.Management.Automation.Language.Parser]::ParseFile(%s, [ref]$null, [ref]$errs); "
            "if ($errs.Count) { $errs | ForEach-Object { [Console]::Error.WriteLine($_.ToString()) }; exit 1 }"
        ) % json.dumps(str(self.installer()))
        parsed = subprocess.run([self.interpreter, "-NoProfile", "-Command", check],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(parsed.returncode, 0, parsed.stderr)


class CopilotRepoDropTestCase(DistTestCase):
    def test_the_skill_lands_where_a_repository_reads_it(self):
        root = DIST / "copilot-repo"
        self.assertTrue((root / ".github" / "skills" / "keel-connect" / "SKILL.md").is_file())
        self.assertTrue((root / "README.md").is_file())

    def test_there_is_no_manifest_and_no_installer(self):
        """Its whole point is that it needs neither: commit the directory, and everyone has it on
        the next `git pull`."""
        root = DIST / "copilot-repo"
        self.assertFalse((root / ".claude-plugin").exists())
        self.assertFalse((root / "extension.yml").exists())
        self.assertFalse((root / "install.sh").exists())


# ======================================================== the one file every host reads (§5.2, D4, D5)


class SkillFileTestCase(DistTestCase):
    """`SKILL.md`'s frontmatter is the whole trigger surface, and its body is the whole reply
    surface. Both are asserted here rather than in the script tests, because both are things a
    *packaging* can silently break and a script test would never see."""

    def text(self):
        return SOURCE_SKILL.read_text(encoding="utf-8")

    def test_the_frontmatter_key_set_is_exactly_three(self):
        block, keys = self.frontmatter(self.text())
        self.assertEqual(set(keys), {"name", "description", "license"},
                         "decision 6: the agentskills.io core every host either honours or "
                         "ignores harmlessly. Every field outside it is one host's private "
                         "extension, and a shared file carrying one means different things in "
                         "different places.")

    def test_the_lengths_the_tightest_host_allows(self):
        block, _ = self.frontmatter(self.text())
        frontmatter = "---\n" + block + "---\n"
        self.assertLess(len(frontmatter), 1024, "frontmatter under 1,024 characters")
        description = re.search(r'^description: "(.*)"$', block, re.M).group(1)
        self.assertLess(len(description.replace('\\"', '"')), 500,
                        "description under 500 characters -- write to the tightest host's rule "
                        "and every host is satisfied")

    def test_the_description_is_trigger_first_and_names_both_jobs(self):
        block, _ = self.frontmatter(self.text())
        description = re.search(r'^description: "(.*)"$', block, re.M).group(1)
        self.assertTrue(description.startswith("Use when"),
                        "decision 5: every host's matcher wants when-to-use, not what-it-does")
        for phrase in ("keel connect", "keel disconnect", "start the keel runtime",
                       "stop the keel runtime", "keel off"):
            self.assertIn(phrase, description, "both jobs' phrasings must be in the one trigger "
                                               "surface every host reads")

    def test_the_name_is_unchanged(self):
        block, _ = self.frontmatter(self.text())
        self.assertIn('name: "keel-connect"', block,
                      "decision 8: the skill of the connection, both directions. A rename would "
                      "break the playground symlink, keel-e2e-eval, and every sentence anyone "
                      "has written about it, in exchange for a noun.")

    def test_every_outcome_section_tells_the_reply_to_name_the_environment(self):
        """X-5, from the other end: the skill relays which Keel it reached, always."""
        text = self.text()
        connect_half, disconnect_half = text.split("## Running the disconnect", 1)
        for half, label in ((connect_half, "connect"), (disconnect_half, "disconnect")):
            with self.subTest(half=label):
                self.assertIn("environment", half,
                              "each half must tell the agent to end its reply naming which Keel")

    def test_no_reply_hard_codes_an_address(self):
        """X-5: the skill carries no base URL and no environment table. The only URLs it may name
        are the Python install pages, which are an operating system's, not a Keel's."""
        allowed = ("https://www.python.org/downloads/",)
        urls = {url.rstrip(".,;:)`>") for url in re.findall(r"https?://\S+", self.text())}
        self.assertEqual(urls - set(allowed), set(),
                         "the Keel that issued a URL is the only thing that knows where its own "
                         "screens are; this file may not carry one")

    def test_d4_no_ecosystem_in_the_skill(self):
        text = self.text().lower()
        for word in ("spec kit", "speckit", "openspec", "superpowers"):
            self.assertNotIn(word, text,
                             "D4: the skill is the same file in every ecosystem, and names none")
        for script in sorted(SOURCE_SCRIPTS.glob("*.py")):
            source = script.read_text(encoding="utf-8").lower()
            for word in ("spec kit", "speckit", "openspec", "superpowers"):
                self.assertNotIn(word, source, "D4, in %s" % script.name)

    def test_d5_no_host_in_a_reply_beyond_the_one_marked_exception(self):
        """The exception is a line telling one host to add a flag -- an instruction to the agent,
        not a sentence anyone reads -- and it must carry the comment that says so."""
        text = self.text()
        hits = [line for line in text.splitlines()
                if re.search(r"copilot|claude code|anthropic", line, re.I)]
        self.assertEqual(len(hits), 1,
                         "D5 allows exactly one line here; found %d: %r" % (len(hits), hits))
        self.assertIn("--host copilot", hits[0])
        self.assertIn("D5 exception, deliberate and the only one in this file", text,
                      "the exception must say in the file that it is one")

    def test_the_python_clause_is_where_a_founder_will_hit_it(self):
        """A-5: a founder with no `python3` at all gets *command not found*, and no script can tell
        them anything -- so the answer lives in the instruction layer, in *Running the check*."""
        text = self.text()
        section = text.split("## Running the check", 1)[1].split("\n## ", 1)[0]
        self.assertIn("Python 3.9 or newer", section)
        for platform_hint in ("xcode-select --install", "winget install", "apt install python3"):
            self.assertIn(platform_hint, section)

    def test_x4_the_development_override_is_named_nowhere(self):
        text = self.text().lower()
        self.assertNotIn("--runtime-path", text)
        self.assertNotIn("keel_runtime_path", text)


if __name__ == "__main__":
    unittest.main()
