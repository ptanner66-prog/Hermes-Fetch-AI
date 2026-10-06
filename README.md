# Hermes Fetch AI

[![CI](https://github.com/ptanner66-prog/Hermes-Fetch-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/ptanner66-prog/Hermes-Fetch-AI/actions/workflows/ci.yml)
[![CodeQL](https://github.com/ptanner66-prog/Hermes-Fetch-AI/actions/workflows/codeql.yml/badge.svg)](https://github.com/ptanner66-prog/Hermes-Fetch-AI/actions/workflows/codeql.yml)

Hermes Fetch AI is a small, policy-aware bridge that lets [Fetch.ai uAgents](https://fetch.ai) call a deliberately allowlisted subset of [Hermes Agent](https://github.com/NousResearch/hermes-agent) tools. Fetch supplies identity, signed envelopes, addressing, discovery rails, and uAgent protocols. Hermes remains the local execution layer. This package is the narrow waist between them: default-deny policy, replay protection, argument validation, response size limits, redacted audit, and a Hermes plugin.

## How it works

```text
remote uAgent
   |  signed ListTools / CallTool (Fetch.ai's published MCP protocol)
   v
bridge uAgent (this package)
   |  rate limits, default-deny policy, replay protection,
   |  schema + URL/shell argument checks
   |  stdio subprocess: filtered environment, timeouts
   v
Hermes tools MCP server (separate process)
   |
   v
size-capped response to the caller + redacted JSONL audit record
```

The bridge never touches the Hermes conversations/messaging surface. See [`docs/architecture.md`](docs/architecture.md) for trust boundaries and design decisions.

## Quickstart (no secrets, no network)

Requires Python 3.11 or 3.12.

```bash
git clone https://github.com/ptanner66-prog/Hermes-Fetch-AI
cd Hermes-Fetch-AI
python -m pip install -e ".[dev]"
hermes-fetch-ai doctor
hermes-fetch-ai demo local      # expect: echo result: hello
```

The demo runs a client uAgent and the bridge uAgent against fake MCP tools, through the same policy path real calls use.

To install without cloning:

```bash
pip install "hermes-fetch-ai @ git+https://github.com/ptanner66-prog/Hermes-Fetch-AI"
```

> Not on PyPI yet. Pushing a `vX.Y.Z` tag runs the release workflow, which verifies, builds, attests, and attaches the wheel and sdist to a GitHub release. PyPI publishing is built in but opt-in (trusted publishing, enabled with the `PUBLISH_TO_PYPI` repository variable); after the first published release, `pip install hermes-fetch-ai` works.

## Connect real Hermes tools

The bridge runs Hermes' tools MCP server as a stdio subprocess, with Hermes and the bridge in separate Python environments. The easiest way is through the Hermes plugin:

1. Install the bridge in its own environment (Python 3.11 or 3.12):

   ```bash
   uv tool install --python 3.12 "hermes-fetch-ai @ git+https://github.com/ptanner66-prog/Hermes-Fetch-AI"
   ```

2. Install and enable the plugin:

   ```bash
   hermes plugins install ptanner66-prog/Hermes-Fetch-AI/hermes-plugin/fetchai-bridge
   hermes plugins enable fetchai-bridge
   ```

3. Give the bridge a stable identity: add `UAGENT_SEED` (at least 32 random characters, never in YAML) to `~/.hermes/.env`, or set the plugin's `uagent_seed` setting in the Desktop app. To generate one:

   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

4. Copy [`examples/hermes-stdio.yaml`](examples/hermes-stdio.yaml) to `bridge.yaml`. Leave `hermes_mcp.command` unset: the plugin hands the bridge Hermes' own interpreter.
5. Check and run it:

   ```bash
   hermes fetchai-bridge doctor --config bridge.yaml
   hermes fetchai-bridge serve --config bridge.yaml
   ```

Without the plugin, set `hermes_mcp.command` in `bridge.yaml` to the Python interpreter of the Hermes environment and use `hermes-fetch-ai doctor` / `hermes-fetch-ai serve` with the same arguments.

Only `skills_list` is public; every other tool the Hermes tools server can expose is denylisted. Callers must follow each tool's served input schema and attach replay metadata; see [`docs/demo.md`](docs/demo.md) for the call shape. If Hermes' tools server cannot start, `serve` exits with `hermes backend: FAIL` and explains how to see the server's error.

## Status

| Tier | What it proves | State |
|------|----------------|-------|
| Local end-to-end | Client uAgent -> bridge uAgent -> MCP tool -> response through the real uAgents dispatcher | Covered by CI on Ubuntu, macOS, and Windows with Python 3.11/3.12 |
| Real HTTP serve smoke | Separate bridge process, signed HTTP envelopes, dynamic port, graceful SIGINT/SIGTERM/SIGBREAK shutdown | Covered by CI; `tests/test_serve_http_roundtrip.py` |
| Hermes-backed | Real Hermes tools through `agent.transports.hermes_tools_mcp_server` as an isolated stdio subprocess | Covered by CI against Hermes 0.21.5 and a pinned `main`; also passed against v0.16.x ([`docs/demo.md`](docs/demo.md)) |
| Hermes plugin | The plugin loads in real Hermes, passes the catalog admission checks, and runs the bridge | Covered by CI against Hermes 0.21.5 and a pinned `main`: `hermes plugins validate --install-deps`, `hermes plugins doctor --ci`, `hermes fetchai-bridge doctor` and `demo local` |
| Agentverse mailbox | Remote uAgent reaches the bridge over Fetch rails | Manual and not yet verified end to end; [`docs/agentverse-mailbox.md`](docs/agentverse-mailbox.md) |

## Hermes compatibility

- **Works with current Hermes.** CI runs the plugin checks and the stdio field test against Hermes 0.21.5, the latest release (Python 3.11), and a pinned `main` (`bb236287`, Python 3.14). Both pin mcp 2.0.0. This package's mcp 1.28.1 client negotiates MCP protocol `2025-11-25`, which the mcp 2.0 server accepts, and the tools server's flat arguments are handled. It also passed against hermes-agent v0.16.x, whose tools server wrapped arguments in one `kwargs` object.
- **Separate environments by design.** Hermes pins `mcp==2.0.0` (and `main` now needs Python 3.14); this package pins `mcp==1.28.1` through uAgents and supports Python 3.11/3.12. The Hermes plugin is a stdlib-only sidecar (`python_runtime: external`), so nothing is installed into Hermes' environment. Only the in-process demo mode needs both in one environment, which works with hermes-agent v0.16.x but not current Hermes.

## Hermes plugin

[`hermes-plugin/fetchai-bridge`](hermes-plugin/fetchai-bridge) is a Hermes directory plugin for Hermes 0.21.5 or later. It is stdlib-only, registers no tools or hooks, and never patches Hermes:

- `hermes fetchai-bridge <args>` runs the separately installed `hermes-fetch-ai` with the same arguments (`doctor`, `demo local`, `serve --config ...`, `probe-hermes`).
- It hands the bridge Hermes' own interpreter and import path, so `serve` starts Hermes' tools server the same way Hermes does for its own integrations.
- It ships an `operate` skill the agent loads with `skill_view("fetchai-bridge:operate")`.
- Settings: `command` (path to `hermes-fetch-ai` if it is not on PATH) and `uagent_seed` (a secret stored as `UAGENT_SEED` in Hermes' `.env`).

Under `plugins.isolation: host`, Hermes skips plugin CLI commands; use `hermes-fetch-ai` directly there. See [`docs/native-hermes-plugin.md`](docs/native-hermes-plugin.md).

## Security defaults

- Default-deny tool calls; the denylist wins over any allowlist.
- `ListTools` output is filtered, rate-limited, and size-capped.
- `CallTool` requires bridge replay/idempotency metadata by default.
- Replay metadata uses a request ID plus issue time; duplicates and stale/future calls are rejected before tool invocation.
- Sender identity is routing evidence, not authorization by itself.
- Arguments are size-limited, schema-validated, and checked for unsupported URL schemes, local/private URL targets (including URLs inside longer text), and shell metacharacters.
- Tool responses returned to remote callers are size-limited with deterministic truncation. They are **not** treated as a data-loss-prevention redaction boundary.
- Audit records omit raw arguments, raw outputs, full sender addresses, seeds, tokens, and keys.
- Production seeds must come from `UAGENT_SEED` and be at least 32 characters; YAML seed/mailbox key material and other credential-shaped config values are rejected.
- If the Hermes backend cannot start, `serve` exits non-zero instead of serving an empty tool list.
- With `publish_manifest: false` (the examples' default), the bridge makes no outbound calls of its own: no Almanac registration, contract lookup, or status reports. Replying to a remote agent can look up that agent's endpoint in the Almanac.
- The bridge consumes the Hermes **tools** MCP server only. The Hermes conversations/messaging MCP surface is explicitly out of scope.
- Chat protocol is out of v1 scope.

See [`docs/security.md`](docs/security.md) and [`SECURITY.md`](SECURITY.md).

## Running in production

- Run `hermes-fetch-ai serve` directly under a supervisor such as systemd with `Restart=on-failure` and `hermes_mcp.command` set to Hermes' Python; startup failures exit non-zero so the supervisor can retry.
- Keep `agent.dev_random_seed: false` (as `examples/hermes-stdio.yaml` does) so the bridge address stays stable; `doctor` and `serve` warn if a config ignores `UAGENT_SEED`.
- Keep `policy.public_tools` empty or tiny. `skills_list` is the only Hermes-backed demo-public tool.
- Read the JSONL audit log and alert on denied spikes, replay denials, `backend unavailable` errors, and send failures.
- With `publish_manifest: false` the bridge is not registered in the Almanac, so only clients configured with its endpoint can reach it. Public discovery (Almanac registration or an Agentverse mailbox) is not covered by CI yet.

Deployment notes, including a systemd unit, are in [`docs/production.md`](docs/production.md).

## Roadmap

- [ ] Release `v1.0.0` and publish to PyPI.
- [x] Catalog-ready Hermes plugin ([`hermes-plugin/fetchai-bridge`](hermes-plugin/fetchai-bridge)), validated against real Hermes in CI.
- [ ] Submit the `plugin-catalog` entry to hermes-agent. Draft and steps: [`docs/upstream-hermes-pr.md`](docs/upstream-hermes-pr.md).
- [ ] Verify the Agentverse mailbox tier and Almanac registration end to end on testnet.
- [ ] Support mcp 2.x and Python 3.13+, so the in-process demo mode also works with current Hermes.
- [ ] Drop the PyNaCl and ecdsa dependency-audit exceptions once upstream allows (see [`docs/security.md`](docs/security.md)).

## Documentation

| Doc | Covers |
|-----|--------|
| [`docs/architecture.md`](docs/architecture.md) | Message flow, trust boundaries, design decisions, failure behavior |
| [`docs/demo.md`](docs/demo.md) | Local demo, Hermes-backed demo, client call shape, field test |
| [`docs/production.md`](docs/production.md) | Secrets, systemd, replay contract, reachability, monitoring |
| [`docs/security.md`](docs/security.md) | Threat model, controls, residual dependency risk |
| [`docs/troubleshooting.md`](docs/troubleshooting.md) | Error messages and what to do about them |
| [`docs/agentverse-mailbox.md`](docs/agentverse-mailbox.md) | Manual Agentverse mailbox setup (unverified) |
| [`docs/native-hermes-plugin.md`](docs/native-hermes-plugin.md) | The `fetchai-bridge` Hermes plugin: install, settings, how it runs the bridge |
| [`docs/upstream-hermes-pr.md`](docs/upstream-hermes-pr.md) | Plan and ready-to-paste text for listing in Hermes |

## Development

- License: MIT. Supported Python: 3.11 and 3.12.
- Required local gate (the same checks CI runs): `doctor`, contamination scan, ruff (lint and format), mypy (strict for the package), pytest with coverage, local demo, package build, twine check, wheel smoke, and dependency audit. Commands are in [`CONTRIBUTING.md`](CONTRIBUTING.md).
- CI: tests on Linux, macOS, and Windows with Python 3.11 and 3.12; an 85% branch-coverage gate that counts the CLI and `serve` subprocesses; the Hermes plugin checks and stdio field test against real Hermes; dependency audit, build verification, CodeQL, and Dependabot. Ruff and mypy are pinned to a minor series so tool releases cannot change the rules underneath CI.

## Scope

This package does not create a new agent framework and does not implement commerce flows, exchange features, or wallet UX beyond uAgents seed/address identity. It is a hardened connection layer for a future agentic economy, not the economy itself.
