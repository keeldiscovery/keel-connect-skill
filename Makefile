# The runtime travels inside the skill (keel-cloud `canon/designs/keel-skill-design.md` §3.1,
# invariant D2). There is one copy of keel-runtime's source in the world and it is in
# keel-runtime; every other copy is made by this build step from one named commit, which is why
# `keel_runtime/` is gitignored here and `RUNTIME_VERSION` -- the record of *which* runtime this
# skill carries -- is not.
#
#   make runtime    copy ../keel-runtime/keel_runtime/ in, and stamp RUNTIME_VERSION
#   make test       this repository's own tests, offline, against fake and real runtimes
#   make clean      remove the copied package and the caches
#
# `make dist` and the four packaging trees are spec `004-skill-packaging`, not this one.

SHELL := /bin/bash

# The sibling checkout the package is copied from. Overridable so CI can point at a fresh clone
# of `keeldiscovery/keel-runtime` rather than a working tree beside this one.
KEEL_RUNTIME_SRC ?= ../keel-runtime

# The interpreter the tests run under. The floor is 3.9 (design §4.1) and the matrix holds
# 3.9-3.13; `make test` runs whichever one is asked for and defaults to the ambient python3.
PYTHON ?= python3

.PHONY: runtime test clean

runtime:
	@set -euo pipefail; \
	src="$(KEEL_RUNTIME_SRC)"; \
	if [ ! -d "$$src/keel_runtime" ]; then \
	  echo "make runtime: $$src has no keel_runtime/ package -- set KEEL_RUNTIME_SRC" >&2; \
	  exit 1; \
	fi; \
	if ! git -C "$$src" rev-parse --git-dir >/dev/null 2>&1; then \
	  echo "make runtime: $$src is not a git checkout; a copy whose provenance cannot be" >&2; \
	  echo "  named is the two-runtimes failure D2 exists to prevent" >&2; \
	  exit 1; \
	fi; \
	if ! commit=$$(git -C "$$src" rev-parse --verify --quiet HEAD); then \
	  echo "make runtime: $$src is not on a commit (no HEAD) -- nothing to name" >&2; \
	  exit 1; \
	fi; \
	if [ -n "$$(git -C "$$src" status --porcelain)" ]; then \
	  echo "make runtime: $$src is dirty. RUNTIME_VERSION would name a commit whose" >&2; \
	  echo "  working tree is not what was copied. Commit or stash there first:" >&2; \
	  git -C "$$src" status --short >&2; \
	  exit 1; \
	fi; \
	version=$$(awk -F'"' '/^__version__/ {print $$2; exit}' "$$src/keel_runtime/__init__.py"); \
	if [ -z "$$version" ]; then \
	  echo "make runtime: no __version__ in $$src/keel_runtime/__init__.py" >&2; \
	  exit 1; \
	fi; \
	tag=$$(git -C "$$src" describe --tags --exact-match 2>/dev/null || true); \
	if [ -n "$$tag" ]; then stamp="$$tag"; else stamp="$$version+$$(git -C "$$src" rev-parse --short HEAD)"; fi; \
	rm -rf keel_runtime; \
	cp -R "$$src/keel_runtime" keel_runtime; \
	find keel_runtime -name '__pycache__' -type d -prune -exec rm -rf {} +; \
	find keel_runtime -name '*.py[co]' -delete; \
	printf '%s\n' "$$stamp" > RUNTIME_VERSION; \
	echo "keel_runtime/ <- $$src at $$commit"; \
	echo "RUNTIME_VERSION: $$stamp"

test:
	$(PYTHON) -m unittest discover tests -v

clean:
	rm -rf keel_runtime
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	find . -name '*.py[co]' -delete
