# Hermes Fetch AI

[![CI](https://github.com/ptanner66-prog/Hermes-Fetch-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/ptanner66-prog/Hermes-Fetch-AI/actions/workflows/ci.yml)
[![CodeQL](https://github.com/ptanner66-prog/Hermes-Fetch-AI/actions/workflows/codeql.yml/badge.svg)](https://github.com/ptanner66-prog/Hermes-Fetch-AI/actions/workflows/codeql.yml)

Hermes Fetch AI is a small, policy-aware bridge that lets Fetch.ai uAgents reach a deliberately allowlisted subset of Hermes Agent tools. Fetch supplies identity, signed envelopes, addressing, discovery rails, and uAgent protocols. Hermes remains the local execution layer. This package is the narrow waist between them: default-deny policy, replay protection, argument validation, response size limits, redacted audit, and a Hermes plugin entry point.

## Status

The bridge runs an end-to-end uAgent round trip: a client uAgent sends `ListTools`/`CallTool` to the bridge uAgent over the signed MCP protocol, the bridge applies policy and replay checks, invokes the local MCP tool backend, and returns a bounded audited response.

| Tier | What it proves | State |
|------|----------------|-------|
| Local end-to-end | Client uAgent -> bridge uAgent -> MCP tool -> response through the real uAgents dispatcher | Covered by CI on Ubuntu, macOS, and Windows with Python 3.11/3.12 |
| Real HTTP serve smoke | Separate bridge process, signed HTTP envelopes, dynamic port, graceful SIGINT/SIGTERM/SIGBREAK shutdown | Covered by CI; `tests/test_serve_http_roundtrip.py` |
| Hermes-backed demo | Real Hermes tools through `agent.transports.hermes_tools_mcp_server` as an isolated stdio subprocess | Gated field test (`docs/demo.md`); see "Hermes compatibility" below |
| Agentverse mailbox | Remote uAgent reaches the bridge over Fetch rails | Manual and not yet verified end to end; [`docs/agentverse-mailbox.md`](docs/agentverse-mailbox.md) |

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

> Release note: pushing a `vX.Y.Z` tag runs the release workflow, which verifies, builds, attests, and attaches the wheel and sdist to a GitHub release. Publishing to PyPI is built in but opt-in (trusted publishing, enabled with the `PUBLISH_TO_PYPI` repository variable) and has not happened yet. Until then, install from a release wheel or from git.

## Hermes plugin entry point

The package exposes a lightweight plugin entry point:

```toml
[project.entry-points."hermes_agent.plugins"]
fetchai = "hermes_fetch_ai.hermes_plugin"
```

That makes the plugin discoverable to Hermes when the package is installed in Hermes' own environment. Hermes loads third-party plugins only after they are enabled (`hermes plugins enable fetchai`). The verified standalone package CLI remains:

```bash
hermes-fetch-ai doctor
hermes-fetch-ai demo local
hermes-fetch-ai serve --config /absolute/path/to/examples/hermes-stdio.yaml
```

Once installed into Hermes' environment and enabled, the plugin delegates to equivalent subcommands:

```bash
hermes fetchai doctor
hermes fetchai probe
hermes fetchai demo local
hermes fetchai serve --config /absolute/path/to/examples/hermes-stdio.yaml
```

The upstream contribution plan is intentionally small: keep this repo standalone and list it through the Hermes plugin catalog. See [`docs/native-hermes-plugin.md`](docs/native-hermes-plugin.md) and [`docs/upstream-hermes-pr.md`](docs/upstream-hermes-pr.md).

## Hermes compatibility

- Field-tested against hermes-agent v0.16.x, where the tools server wrapped tool arguments in one `kwargs` object.
- Current hermes-agent `main` develops on Python 3.14, pins `mcp==2.0.0` in its `[mcp]` extra, and serves flat tool arguments. This package pins `mcp==1.28.1` (via uAgents) and Python 3.11/3.12, so it cannot be installed into a current Hermes environment, which also rules out the in-process mode and the `hermes fetchai` plugin there. Run it from its own environment in stdio mode with `hermes_mcp.command` pointing at Hermes' Python.

## Security defaults

- Default-deny tool calls.
- `ListTools` output is filtered, rate-limited, and size-capped.
- `CallTool` requires bridge replay/idempotency metadata by default.
- Replay metadata uses a request ID plus issue time; duplicates and stale/future calls are rejected before tool invocation.
- Sender identity is routing evidence, not authorization by itself.
- Arguments are size-limited, schema-validated, and checked for unsupported URL schemes, local/private URL targets, and shell-control characters.
- Tool responses returned to remote callers are size-limited with deterministic truncation. They are **not** treated as a data-loss-prevention redaction boundary.
- Audit records omit raw arguments, raw outputs, full sender addresses, seeds, tokens, and keys.
- Production seeds must come from `UAGENT_SEED` and be at least 32 characters; YAML seed/mailbox key material and other credential-shaped config values are rejected.
- If the Hermes backend cannot start, `serve` exits non-zero with `hermes backend: FAIL` instead of serving an empty tool list.
- The bridge consumes the Hermes **tools** MCP server only. The Hermes conversations/messaging MCP surface is explicitly out of scope.
- Chat protocol is out of v1 scope.

See [`docs/security.md`](docs/security.md) and [`SECURITY.md`](SECURITY.md).

## Minimal production shape

1. Install the package in its own virtual environment (Python 3.11 or 3.12).
2. Set `UAGENT_SEED` (at least 32 random characters) from a secret manager or a `0600` environment file; never put it in YAML.
3. Copy `examples/hermes-stdio.yaml` and set `hermes_mcp.command` to the Python interpreter of the Hermes environment. It keeps `agent.dev_random_seed: false`, so the bridge identity stays stable across restarts.
4. Start `hermes-fetch-ai serve --config /absolute/path/to/hermes-stdio.yaml` under a supervisor such as systemd with `Restart=on-failure`.
5. Keep `policy.public_tools` empty or tiny. `skills_list` is the only Hermes-backed demo-public tool.
6. Read the JSONL audit log and alert on denied spikes, replay denials, `backend unavailable` errors, and send failures.

With `publish_manifest: false` the bridge is not registered in the Almanac, so only clients configured with its endpoint can reach it. Public discovery (Almanac registration or an Agentverse mailbox) is not covered by CI yet.

Deployment notes are in [`docs/production.md`](docs/production.md).

## Repository hygiene

- License: MIT.
- Supported Python: 3.11 and 3.12.
- Required local gate: `doctor`, contamination scan, ruff, mypy, pytest, local demo, package build, twine check, wheel smoke, and dependency audit.
- CI: OS/Python matrix, security audit, build verification, CodeQL, Dependabot. Ruff and mypy are pinned to a minor series so tool releases cannot change the rules underneath CI.
- Contributions: see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Scope

This package does not create a new agent framework and does not implement commerce flows, exchange features, or wallet UX beyond uAgents seed/address identity. It is a hardened connection layer for a future agentic economy, not the economy itself.
