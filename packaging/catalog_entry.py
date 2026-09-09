#!/usr/bin/env python3
"""Writes `dist/speckit-catalog-entry.json` from the **built** `extension.yml`.

A build tool, not a shipped file: it lives in `packaging/` and never appears in any of the four
trees. `make dist` runs it as the last step of the Spec Kit tree.

**Why it is generated rather than typed.** The catalogue entry is what the founder pastes into the
Spec Kit *Extension Submission* issue (keel-cloud `canon/designs/keel-skill-design.md` §8.4, steps
5 and 6). A hand-written entry and a built manifest are two statements of one fact, and the day
they disagree is the day the submission is rejected for a reason nobody can see. Every field below
that has a counterpart in the manifest is read from it.

`verified`, `downloads`, `stars`, `created_at` and `updated_at` are the maintainers' and the
system's, and are deliberately **not** emitted -- step 6 says do not send values for them.

Standard library only, and no `pyyaml`: the manifest this reads is one we generate ourselves from
a template in this repository, in a fixed and simple shape, so a small reader is honest here where
it would not be against a stranger's YAML. It fails loudly rather than guessing.
"""
import json
import os
import re
import sys


def read_manifest(path):
    """The handful of fields the catalogue entry needs, from our own generated manifest."""
    text = open(path, "r").read()

    def scalar(key, block=None):
        haystack = text if block is None else block
        match = re.search(r"^\s*%s:\s*(.+?)\s*$" % re.escape(key), haystack, re.M)
        if match is None:
            raise SystemExit("catalog_entry.py: %s has no '%s:'" % (path, key))
        return match.group(1).strip().strip('"').strip("'")

    extension_block = text.split("extension:", 1)[1].split("\nrequires:", 1)[0]
    requires_block = text.split("requires:", 1)[1].split("\nprovides:", 1)[0]

    tags_line = scalar("tags")
    tags = [t.strip() for t in tags_line.strip("[]").split(",") if t.strip()]

    return {
        "id": scalar("id", extension_block),
        "name": scalar("name", extension_block),
        "version": scalar("version", extension_block),
        "description": scalar("description", extension_block),
        "author": scalar("author", extension_block),
        "repository": scalar("repository", extension_block),
        "license": scalar("license", extension_block),
        "speckit_version": scalar("speckit_version", requires_block),
        "commands": len(re.findall(r"name:\s*speckit\.", text)),
        "tags": tags,
    }


def build_entry(manifest):
    repository = manifest["repository"]
    version = manifest["version"]
    return {
        "id": manifest["id"],
        "name": manifest["name"],
        "description": manifest["description"],
        "author": manifest["author"],
        "version": version,
        # One of the two accepted shapes; a release must actually exist at this tag, not merely a
        # tag (§8.4 step 3).
        "download_url": "%s/archive/refs/tags/v%s.zip" % (repository, version),
        "repository": repository,
        "documentation": "%s#readme" % repository,
        "changelog": "%s/blob/main/CHANGELOG.md" % repository,
        "license": manifest["license"],
        "category": "integration",
        # Neither command writes anything itself -- connect only checks and starts the runtime,
        # brief only hands the agent words to read. A spec edit that follows is the agent's own
        # act, as it would be from any prompt (X-6).
        "effect": "read-only",
        "requires": {
            "speckit_version": manifest["speckit_version"],
            "tools": [{"name": "python3", "version": ">=3.9", "required": True}],
        },
        "provides": {"commands": manifest["commands"], "hooks": 0},
        "tags": manifest["tags"],
    }


def main(argv):
    if len(argv) != 3:
        raise SystemExit("usage: catalog_entry.py <built extension.yml> <output.json>")
    manifest = read_manifest(argv[1])
    entry = build_entry(manifest)
    directory = os.path.dirname(os.path.abspath(argv[2]))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with open(argv[2], "w") as handle:
        json.dump(entry, handle, indent=2, sort_keys=False)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
