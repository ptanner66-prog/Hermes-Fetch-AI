# Hermes Fetch AI

[![CI](https://github.com/ptanner66-prog/Hermes-Fetch-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/ptanner66-prog/Hermes-Fetch-AI/actions/workflows/ci.yml)
[![CodeQL](https://github.com/ptanner66-prog/Hermes-Fetch-AI/actions/workflows/codeql.yml/badge.svg)](https://github.com/ptanner66-prog/Hermes-Fetch-AI/actions/workflows/codeql.yml)

Hermes Fetch AI is a small, policy-aware bridge that lets Fetch.ai uAgents reach a deliberately allowlisted subset of Hermes Agent tools. Fetch supplies identity, signed envelopes, addressing, discovery rails, and uAgent protocols. Hermes remains the local execution layer. This package is the narrow waist between them: default-deny policy, replay protection, argument validation, response size limits, redacted audit, and a Hermes plugin entry point.

## Status

The bridge runs an end-to-end uAgent round trip: a client uAgent sends `ListTools`/`CallTool` to the bridge uAgent over the signed MCP protocol, the bridge applies policy and replay checks, invokes the local MCP tool backend, and returns a bounded audited response.

| Tier | What it proves | State |
|------|----------------|-------|
| Local end-to-end | Client uAgent -> bridge uAgent -> MCP tool -> response through the real uAgents dispatcher | Green in CI on Python 3.11/3.12 |
| Real HTTP serve smoke | Separate bridge process, signed HTTP envelopes, dynamic port, graceful SIGINT/SIGTERM/SIGBREAK shutdown | Green; covered by `tests/test_serve_http_roundtrip.py` |
| Hermes-backed demo | Real Hermes tools through `agent.transports.hermes_tools_mcp_server` as an isolated stdio subprocess | Gated field test; depends on a Hermes build that exposes that tools server |
| Agentverse mailbox | Remote uAgent reaches the bridge over Fetch rails | Operator tier; requires `UAGENT_SEED` and Agentverse mailbox setup |

The local tier requires no secrets, hosted services, or network:

```bash
python -m pip install -e .[dev]
python -m hermes_fetch_ai.cli doctor
python -m hermes_fetch_ai.cli demo local
```

Installed package users can run the package CLI directly:

```bash
pip install hermes-fetch-ai
hermes-fetch-ai doctor
hermes-fetch-ai demo local
```

> Current release note: the GitHub release workflow builds and attests artifacts. It does not yet publish to PyPI, so `pip install hermes-fetch-ai` is the intended package command once an artifact is published to the selected package index.

## Hermes plugin entry point

The package exposes a lightweight plugin entry point:

```toml
[project.entry-points."hermes_agent.plugins"]
fetchai = "hermes_fetch_ai.hermes_plugin"
```

That makes the plugin discoverable to Hermes. Current Hermes installations may still require explicit plugin enablement, for example by enabling `fetchai` in Hermes plugin configuration, before `hermes fetchai ...` is wired into the Hermes CLI. The verified standalone package CLI remains:

```bash
hermes-fetch-ai doctor
hermes-fetch-ai demo local
hermes-fetch-ai serve --config /absolute/path/to/examples/hermes-stdio.yaml
```

If enabled in Hermes and the active Hermes build wires entry-point plugin CLI commands, the plugin delegates to equivalent subcommands:

```bash
hermes fetchai doctor
hermes fetchai probe
hermes fetchai demo local
hermes fetchai serve --config /absolute/path/to/examples/hermes-stdio.yaml
```

The upstream contribution plan is intentionally small: keep this repo standalone, then ask Hermes maintainers whether they want a docs/catalog/setup entry that installs and enables the plugin. See [`docs/native-hermes-plugin.md`](docs/native-hermes-plugin.md).

## Security defaults

- Default-deny tool calls.
- `ListTools` output is filtered, rate-limited, and size-capped.
- `CallTool` requires bridge replay/idempotency metadata by default.
- Replay metadata uses a request ID plus issue time; duplicates and stale/future calls are rejected before tool invocation.
- Sender identity is routing evidence, not authorization by itself.
- Arguments are size-limited, schema-validated, and checked for unsupported URL schemes, local/private URL targets, and shell-control characters.
- Tool responses returned to remote callers are size-limited with deterministic truncation. They are **not** treated as a data-loss-prevention redaction boundary.
- Audit records omit raw arguments, raw outputs, full sender addresses, seeds, tokens, and keys.
- Production seeds must come from `UAGENT_SEED`; YAML seed/mailbox key material is rejected.
- The bridge consumes the Hermes **tools** MCP server only. The Hermes conversations/messaging MCP surface is explicitly out of scope.
- Chat protocol is out of v1 scope.

See [`docs/security.md`](docs/security.md) and [`SECURITY.md`](SECURITY.md).

## Minimal production shape

1. Install the package in the Hermes environment.
2. Enable the Hermes plugin only if the active Hermes build supports entry-point plugin CLI wiring; otherwise use `hermes-fetch-ai` directly.
3. Set `UAGENT_SEED` from a secret manager or a `0600` environment file; never put it in YAML.
4. Start `hermes-fetch-ai serve --config /absolute/path/to/hermes-stdio.yaml`.
5. Keep `policy.public_tools` empty or tiny. `skills_list` is the only Hermes-backed demo-public tool.
6. Read the JSONL audit log and alert on denied spikes, replay denials, and send failures.

Deployment notes are in [`docs/production.md`](docs/production.md).

## Repository hygiene

- License: MIT.
- Supported Python: 3.11 and 3.12.
- Required local gate: `doctor`, contamination scan, ruff, mypy, pytest, local demo, package build, twine check, wheel smoke, and dependency audit.
- CI: OS/Python matrix, security audit, build verification, CodeQL, Dependabot.
- Contributions: see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Scope

This package does not create a new agent framework and does not implement commerce flows, exchange features, or wallet UX beyond uAgents seed/address identity. It is a hardened connection layer for a future agentic economy, not the economy itself.
