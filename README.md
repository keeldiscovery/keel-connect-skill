# keel-connect-skill

A Claude Code skill: when a user says or clearly means "keel connect", check whether a local
`keel-runtime` process (from the `keel-cloud` repository's spec 020/021) is already running and
connected to Keel Cloud, and if not, start `keel connect` for them and hand back the code/URL they
need to approve it.

This is a **Claude-Code-hosted** skill (real shell access, `SKILL.md` + a script) -- not to be
confused with the unrelated `keel-discovery` skill in the `keel-skill` repository, which is
MCP-hosted, has no shell access at all, and interprets Keel's product discovery protocol. The two
share a product name and nothing else; see `SKILL.md`'s own "what this skill deliberately does not
do" section.

## Layout

- `SKILL.md` -- trigger condition and outcome-interpretation instructions for Claude.
- `scripts/keel_connect_check.py` -- the entire implementation. Stdlib-only Python, invoked as a
  subprocess; never imported as a library.
- `specs/001-keel-connect-check/` -- spec-kit-style design docs (`spec.md`, `plan.md`,
  `research.md`, `tasks.md`, `contracts/skill-script-output.md`).
- `tests/` -- this repository's own unit tests, run entirely against a fake runtime in
  `tests/fixtures/` that this repository fully controls.

## Running the script by hand

```sh
python3 scripts/keel_connect_check.py --runtime-path <path-to-a-keel-cloud checkout>/keel-runtime
# {"outcome": "authorization_started", "user_code": "...", "verification_uri": "...", ...}
# or {"outcome": "already_connected", ...} / "connected" / "authorization_pending_timeout" /
# "runtime_unavailable" / "internal_error"
```

With a packaged `keel-runtime` install (once `keel-cloud`'s spec 020 `pyproject.toml` ships it),
no `--runtime-path` is needed -- a `keel` command on `PATH` is tried first. See
`specs/001-keel-connect-check/contracts/skill-script-output.md` for the exhaustive, stable output
contract this script guarantees.

## Running the tests

```sh
python3 -m unittest discover tests -v
```

Every outcome branch, the `PATH`-vs-`--runtime-path` resolution order, and the bounded-wait timeout
behavior are covered here, entirely offline, against the fake runtime fixtures in `tests/fixtures/`
-- no real `keel-runtime` install and no real Keel Cloud server are used anywhere in this
repository's own test suite.

## The real three-tier proof lives elsewhere

This repository proves the script's own logic in isolation. The real end-to-end chain -- this
script, launching a real `keel-runtime`, talking to a real Keel Cloud server -- is proven by
`KeelConnectSkillJourneyTest` in the `keel-cloud` repository
(`src/test/java/com/keeldiscovery/cloud/acceptance/KeelConnectSkillJourneyTest.java`), which shells
out to this repository's `scripts/keel_connect_check.py` directly against a live Testcontainers-backed
Keel Cloud instance and a real runtime subprocess it launches.

## Dependencies

None beyond the Python standard library, matching `keel-runtime`'s own posture -- this script must
run on a bare `python3`, since Claude Code invokes it as a plain subprocess with nothing installed.
