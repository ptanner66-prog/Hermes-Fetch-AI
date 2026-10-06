# Changelog

All notable changes are documented here. The project follows [semantic versioning](https://semver.org/).

## 1.0.0 - Unreleased

The first release. To release, set the date here and push the `v1.0.0` tag.

### Bridge

- A uAgents bridge that serves Fetch's MCP message models (`ListTools`, `CallTool`) over signed uAgents envelopes and runs the calls against Hermes' tools MCP server, or against two built-in fake tools for demos and tests.
- Backends: Hermes' tools server as a stdio subprocess (the production shape, tested against Hermes 0.21.5 and `main`); an in-process mode for hermes-agent v0.16.x; fake tools.
- CLI: `doctor` (version, config, dependency pins), `probe-hermes`, `demo local` (a two-agent round trip with no network), `demo mailbox`, and `serve`.
- `serve` exits with status 1 and a clear message when Hermes' tools server or the HTTP server cannot start, and shuts down cleanly on Ctrl-C or SIGTERM.
- Example configs for a local demo, Hermes over stdio, the in-process mode, and an Agentverse mailbox, plus a client, `examples/call_bridge.py`, that calls a running bridge.

### Security

- Default deny: a tool is callable only if it is public or allowlisted for the sender, and the denylist always wins. The Hermes example configs make only `skills_list` public.
- Replay protection for `CallTool`: a per-sender request ID and an issue time, checked for freshness, with a bounded in-memory cache.
- Rate limits per sender and globally, for both `ListTools` and `CallTool`.
- Argument checks: each tool's JSON schema, shell metacharacters and control characters, and URLs anywhere in the arguments, including encoded IPv4 forms and DNS answers that point at private or local addresses.
- Size caps on arguments, tool lists, and results; tool names restricted to plain ASCII.
- A JSONL audit log with an allowlist of fields (no arguments or outputs) and redaction.
- Seeds come only from `UAGENT_SEED` and must be at least 32 characters; config files that contain credential-shaped values are rejected.
- With `publish_manifest: false`, the bridge makes no outbound calls of its own: it skips the Almanac contract lookup and the status reports that uAgents otherwise makes for every agent.
- Hermes' tools server runs without a shell, with an environment allowlist and its stderr discarded.
- Dependencies pinned to tested versions, including `mcp` 1.28.1 (PYSEC-2026-3483); builds use `setuptools>=83` (PYSEC-2026-3447).

### Hermes plugin

- `hermes-plugin/fetchai-bridge`, a directory plugin for Hermes 0.21.5 or later. It is stdlib-only (`python_runtime: external`), adds `hermes fetchai-bridge`, which runs the separately installed bridge with an environment allowlist and hands it Hermes' interpreter, and ships an `operate` skill.
- A draft entry for Hermes' plugin catalog (`upstream/hermes-pr/plugin-catalog/fetchai-bridge.yaml`) and submission notes.

### Quality

- CI on Linux, macOS, and Windows with Python 3.11 and 3.12: ruff lint and format, `mypy --strict`, and the test suite, including a real HTTP round trip through `serve`.
- At least 90% branch coverage, counting the CLI and `serve` subprocesses.
- A CI job against Hermes 0.21.5 and a pinned `main`: Hermes' own plugin validator and doctor, the plugin's CLI, and a field test against Hermes' real tools server.
- Dependency audit, CodeQL, Dependabot, wheel and sdist checks, and a release workflow that can publish to PyPI through trusted publishing.

### Known limitations

- The Agentverse mailbox mode has not been verified end to end.
- `serve` listens on all network interfaces; firewall the port.
- The replay cache is in memory, and URL checks cannot stop DNS rebinding or redirects. See [`docs/security.md`](docs/security.md#residual-risks).
- The dependency audit ignores two transitive vulnerabilities with no fix that uAgents can use yet (`CVE-2025-69277` in PyNaCl and `PYSEC-2026-1325` in ecdsa); the reasons are in `docs/security.md`.
