#!/usr/bin/env bash
# install.sh -- copy this skill into a directory an agent reads. That is the whole installer.
#
# keel-cloud `canon/designs/keel-skill-design.md` §8.3, decision 13: the personal install is a
# **flag on the bare tree**, not a fifth packaging, because a second tree of identical bytes is a
# copy to keep honest for no gain.
#
#   ./install.sh --host claude   [--project]   ~/.claude/skills/   or  ./.claude/skills/
#   ./install.sh --host copilot  [--project]   ~/.copilot/skills/  or  ./.github/skills/
#   ./install.sh --host agents                 ~/.agents/skills/   -- more than one agent reads it
#
#   --dest DIR    put it somewhere else entirely; --host is then not needed
#   --dry-run     say where it would go and copy nothing
#   --force       replace an existing install without asking
#
# It copies one directory. It edits no `PATH`, no shell profile and no configuration file
# (invariant X-6), writes nothing outside the destination, and needs no network.
#
# bash 3.2 compatible (macOS ships it). No GNU-only flags.

set -eu

SRC="$(cd "$(dirname "$0")" && pwd)/keel-connect"
SKILL_NAME="keel-connect"
HOST=""
PROJECT=0
DEST=""
DRY_RUN=0
FORCE=0

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --host)     HOST="${2:-}"; shift 2 ;;
    --host=*)   HOST="${1#--host=}"; shift ;;
    --dest)     DEST="${2:-}"; shift 2 ;;
    --dest=*)   DEST="${1#--dest=}"; shift ;;
    --project)  PROJECT=1; shift ;;
    --dry-run)  DRY_RUN=1; shift ;;
    --force)    FORCE=1; shift ;;
    -h|--help)  usage 0 ;;
    *) printf 'install.sh: unknown argument %s\n\n' "$1" >&2; usage 2 ;;
  esac
done

if [ ! -d "$SRC" ]; then
  printf 'install.sh: no %s/ beside this script -- this distribution is incomplete.\n' \
    "$SKILL_NAME" >&2
  exit 1
fi
if [ ! -f "$SRC/SKILL.md" ] || [ ! -f "$SRC/scripts/keel_connect_check.py" ]; then
  printf 'install.sh: %s/ is missing SKILL.md or scripts/ -- this distribution is incomplete.\n' \
    "$SKILL_NAME" >&2
  exit 1
fi
if [ ! -f "$SRC/keel_runtime/__main__.py" ]; then
  printf 'install.sh: %s/ carries no keel_runtime/ -- the runtime is supposed to travel inside\n' \
    "$SKILL_NAME" >&2
  printf '  the skill, and without it nothing here can start a Keel. Re-download in full.\n' >&2
  exit 1
fi

if [ -z "$DEST" ]; then
  case "$HOST" in
    claude)
      if [ "$PROJECT" = "1" ]; then DEST="$PWD/.claude/skills"; else DEST="$HOME/.claude/skills"; fi ;;
    copilot)
      if [ "$PROJECT" = "1" ]; then DEST="$PWD/.github/skills"; else DEST="$HOME/.copilot/skills"; fi ;;
    agents)
      # Read by more than one agent, which is the answer to "I use both". Not the default,
      # because a person with one agent is better served by that agent's own directory -- the one
      # its own tooling can list and remove.
      if [ "$PROJECT" = "1" ]; then
        printf 'install.sh: --host agents has no project location; drop --project.\n' >&2
        exit 2
      fi
      DEST="$HOME/.agents/skills" ;;
    "")
      printf 'install.sh: say where it goes -- --host claude|copilot|agents, or --dest DIR.\n\n' >&2
      usage 2 ;;
    *)
      printf 'install.sh: unknown host %s (claude, copilot, agents).\n\n' "$HOST" >&2
      usage 2 ;;
  esac
fi

TARGET="$DEST/$SKILL_NAME"

printf 'keel-connect -> %s\n' "$TARGET"
if [ "$DRY_RUN" = "1" ]; then
  printf '(--dry-run: nothing copied)\n'
  exit 0
fi

if [ -e "$TARGET" ] && [ "$FORCE" != "1" ]; then
  printf 'There is already something at %s.\n' "$TARGET" >&2
  printf 'Re-run with --force to replace it.\n' >&2
  exit 1
fi

mkdir -p "$DEST"
rm -rf "$TARGET"
cp -R "$SRC" "$TARGET"
# Caches from whoever built or ran this copy are nobody else's business.
find "$TARGET" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$TARGET" -name '*.pyc' -delete 2>/dev/null || true

printf 'Installed.\n'
if command -v python3 >/dev/null 2>&1; then
  pv="$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo '?')"
  if python3 -c 'import sys;sys.exit(0 if sys.version_info>=(3,9) else 1)' 2>/dev/null; then
    printf 'Python %s -- clears the 3.9 floor. Say "keel connect" in your agent.\n' "$pv"
  else
    printf 'Python %s is below the 3.9 Keel needs. Install a newer one once, then say\n' "$pv"
    printf '  "keel connect" in your agent.\n'
  fi
else
  printf 'No python3 found. Keel needs Python 3.9 or newer, installed once:\n'
  printf '  macOS   xcode-select --install, or https://www.python.org/downloads/\n'
  printf '  Windows winget install Python.Python.3.12\n'
  printf '  Linux   your package manager, e.g. sudo apt install python3\n'
fi
