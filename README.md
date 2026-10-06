# Hermes Fetch AI

[![CI](https://github.com/ptanner66-prog/Hermes-Fetch-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/ptanner66-prog/Hermes-Fetch-AI/actions/workflows/ci.yml)
[![CodeQL](https://github.com/ptanner66-prog/Hermes-Fetch-AI/actions/workflows/codeql.yml/badge.svg)](https://github.com/ptanner66-prog/Hermes-Fetch-AI/actions/workflows/codeql.yml)

Hermes Fetch AI lets agents on Fetch.ai's network (uAgents) call a small, explicitly allowed set of tools from a local [Hermes Agent](https://github.com/NousResearch/hermes-agent) install. Each signed request is checked against a default-deny policy, replay protection, and argument checks. The tool runs in Hermes' tools server, a separate process, and the caller gets a size-capped result. Every decision is written to a redacted audit log. A Hermes plugin adds `hermes fetchai-bridge` to Hermes.

Hermes Fetch AI is an independent community project, not affiliated with or endorsed by Fetch.ai or Nous Research.

## How it works

```text
remote uAgent
   |  signed ListTools / CallTool messages (Fetch.ai's MCP message models)
   v
bridge uAgent (this package)
   |  rate limits, default-deny policy, replay protection,
   |  schema + URL/shell argument checks
   |  stdio subprocess with a filtered environment and timeouts
   v
Hermes tools MCP server (separate process)
   |
   v
size-capped response to the caller + redacted JSONL audit record
```

The bridge never touches Hermes' conversations and messaging surface. See [`docs/architecture.md`](docs/architecture.md) for trust boundaries and design decisions.

Terms used below:

- **uAgent**: an agent on Fetch.ai's network. Its address (`agent1q...`) is derived from a secret seed, and every message it sends is signed.
- **Almanac**: Fetch.ai's directory of agent addresses and endpoints, kept in a ledger contract and served by Agentverse's API.
- **Agentverse**: Fetch.ai's hosted service; its mailbox relays messages to agents that aren't publicly reachable.
- **MCP**: the Model Context Protocol. Hermes serves its tools over MCP, and uAgents carry MCP `ListTools`/`CallTool` messages.

## Quickstart (no secrets, no network)

Requires Python 3.11 or 3.12.

```bash
git clone https://github.com/ptanner66-prog/Hermes-Fetch-AI
cd Hermes-Fetch-AI
python -m pip install -e ".[dev]"
hermes-fetch-ai doctor
hermes-fetch-ai demo local      # expect: echo result: hello
```

The demo runs a client uAgent and the bridge uAgent against fake tools, through the same policy path real calls use. To call a running bridge over HTTP instead:

```bash
hermes-fetch-ai serve --config examples/local-direct.yaml
# logs: Starting agent with address: agent1q...
python examples/call_bridge.py agent1q... http://127.0.0.1:8001/submit   # in another terminal
```

To install without cloning:

```bash
pip install "hermes-fetch-ai @ git+https://github.com/ptanner66-prog/Hermes-Fetch-AI"
```

> Not on PyPI yet. Pushing a `vX.Y.Z` tag runs the release workflow, which verifies, builds, attests, and attaches the wheel and sdist to a GitHub release. PyPI publishing is built in but opt-in (trusted publishing, enabled with the `PUBLISH_TO_PYPI` repository variable).

## Connect real Hermes tools

The bridge runs Hermes' tools MCP server as a stdio subprocess, with Hermes and the bridge in separate Python environments. The Hermes plugin makes this one command:

1. Install the bridge in its own environment (Python 3.11 or 3.12), with [uv](https://docs.astral.sh/uv/) or pipx:

   ```bash
   uv tool install --python 3.12 "hermes-fetch-ai @ git+https://github.com/ptanner66-prog/Hermes-Fetch-AI"
   ```

2. Install and enable the plugin:

   ```bash
   hermes plugins install ptanner66-prog/Hermes-Fetch-AI/hermes-plugin/fetchai-bridge
   hermes plugins enable fetchai-bridge
   ```

3. Give the bridge a stable identity: add `UAGENT_SEED` (at least 32 random characters, never in YAML) to `$HERMES_HOME/.env` (default `~/.hermes/.env`), or set the plugin's `uagent_seed` setting in the Desktop app. To generate one:

   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

4. Get the example config, and leave `hermes_mcp.command` unset; the plugin hands the bridge Hermes' own interpreter:

   ```bash
   curl -fsSLo bridge.yaml https://raw.githubusercontent.com/ptanner66-prog/Hermes-Fetch-AI/main/examples/hermes-stdio.yaml
   ```

5. Check and run it:

   ```bash
   hermes fetchai-bridge probe-hermes      # expect: hermes_tools_server: importable
   hermes fetchai-bridge doctor --config bridge.yaml
   hermes fetchai-bridge serve --config bridge.yaml
   ```

Without the plugin, set `hermes_mcp.command` in `bridge.yaml` to the Python interpreter of the Hermes environment and run `hermes-fetch-ai doctor` / `hermes-fetch-ai serve` with the same arguments.

In this config only `skills_list` is public. It returns the name, description, and category of every installed skill, including skills you or the agent wrote, so remove it from `public_tools` if that is sensitive. Every other tool Hermes' tools server offers is denylisted. To give one agent more, list the tools for its address and remove them from `denied_tools` (the denylist always wins):

```yaml
policy:
  allowed_senders:
    agent1q...: [web_search]
```

Callers must follow each tool's input schema and attach replay-protection metadata; [`examples/call_bridge.py`](examples/call_bridge.py) shows a complete client. If Hermes' tools server cannot start, `serve` exits with `hermes backend: FAIL` and names the command to run by hand to see why.

## Status

| Tier | What it proves | State |
|------|----------------|-------|
| Local end-to-end | Client uAgent -> bridge uAgent -> MCP tool -> response, through the real uAgents dispatcher | CI on Linux, macOS, and Windows with Python 3.11/3.12 |
| Real HTTP serve | A separate bridge process, signed HTTP envelopes, fake tools and a stdio MCP server, the example client, and graceful shutdown on SIGTERM (Linux/macOS) and CTRL_BREAK (Windows) | CI; `tests/test_serve_http_roundtrip.py` |
| Hermes-backed | Real Hermes tools through `agent.transports.hermes_tools_mcp_server` as a stdio subprocess | CI against Hermes 0.21.5 and a pinned `main`; also passed by hand against v0.16.x ([`docs/demo.md`](docs/demo.md)) |
| Hermes plugin | The plugin loads in real Hermes and runs the bridge | CI against Hermes 0.21.5 and a pinned `main`: `hermes plugins validate --install-deps` and `hermes plugins doctor --ci` pass, and `hermes fetchai-bridge doctor` and `demo local` work |
| Agentverse mailbox | A remote uAgent reaches the bridge through Agentverse | Manual and not yet verified end to end; [`docs/agentverse-mailbox.md`](docs/agentverse-mailbox.md) |

## Hermes compatibility

- **Tested Hermes versions.** CI runs the plugin checks and the stdio field test against Hermes 0.21.5, the latest release (Python 3.11), and a pinned `main` (`bb236287`, Python 3.14). Both pin mcp 2.0.0. This package's mcp 1.28.1 client negotiates MCP protocol `2025-11-25`, which the mcp 2.0 server accepts. It also passed against hermes-agent v0.16.x.
- **Separate environments by design.** Hermes pins `mcp==2.0.0`, and `main` supports only Python 3.14. This package pins `mcp==1.28.1`, the version it is tested with, and supports Python 3.11/3.12, so the two cannot share an environment today. The plugin is a stdlib-only sidecar (`python_runtime: external`), so nothing is installed into Hermes' environment. Only the in-process mode (`examples/hermes-local.yaml`) needs both in one environment, which works with hermes-agent v0.16.x but not current Hermes.

## Hermes plugin

[`hermes-plugin/fetchai-bridge`](hermes-plugin/fetchai-bridge) is a Hermes directory plugin. It requires Hermes 0.21.5 or later; CI tests 0.21.5 and a pinned `main`. It is stdlib-only, registers no tools or hooks, and never patches Hermes:

- `hermes fetchai-bridge <args>` runs the separately installed `hermes-fetch-ai` with the same arguments (`doctor`, `demo local`, `serve --config ...`, `probe-hermes`).
- It hands the bridge Hermes' interpreter and import path, so `serve` starts Hermes' tools server the way Hermes does, and it passes the bridge only an allowlisted environment, so Hermes' provider API keys never reach it.
- It ships an `operate` skill the agent loads with `skill_view("fetchai-bridge:operate")`.
- Settings: `command` (the path to `hermes-fetch-ai` if it is not on PATH) and `uagent_seed` (a secret stored as `UAGENT_SEED` in Hermes' `.env`).

Details and the full list of what it does are in [`docs/hermes-plugin.md`](docs/hermes-plugin.md) and the [plugin README](hermes-plugin/fetchai-bridge/README.md).

## Security defaults

- Tool calls are default-deny, and the denylist wins over any allowlist.
- A verified signature proves which agent address sent a message but grants nothing by itself: an address can call a tool only if the tool is in `public_tools` or listed for that address in `allowed_senders`.
- `ListTools` output is filtered, rate-limited, and size-capped.
- `CallTool` requires replay-protection metadata (a request ID and issue time) by default; duplicate, stale, or future-dated calls are rejected before the tool runs.
- Arguments are size-limited, schema-validated, and checked for unsupported URL schemes, private or local URL targets (including encoded IP forms and URLs inside longer text), and shell metacharacters.
- Tool responses are size-limited with deterministic truncation. They are **not** redacted; only expose tools whose output is safe for the caller.
- Audit records omit arguments, outputs, full sender addresses, seeds, tokens, and keys.
- Production seeds come only from `UAGENT_SEED` and must be at least 32 characters; credential-shaped values in config files are rejected.
- With `publish_manifest: false` (the default), the bridge makes no outbound calls of its own: no Almanac registration, contract lookup, or status reports. Replying to a remote agent can look up that agent's endpoint in the Almanac.
- The bridge listens on all interfaces (`0.0.0.0`) on `agent.port`; uAgents has no bind-address setting, so firewall the port.
- If Hermes' tools server cannot start, `serve` exits non-zero instead of serving an empty tool list.
- The bridge uses Hermes' **tools** MCP server only; the conversations/messaging surface is out of scope, and so is the chat protocol.

Residual risks are listed in [`docs/security.md`](docs/security.md); to report a vulnerability, see [`SECURITY.md`](SECURITY.md).

## Running in production

- Run `hermes-fetch-ai serve` under a supervisor such as systemd with `Restart=on-failure` and `hermes_mcp.command` set to Hermes' Python; startup failures exit non-zero so the supervisor can retry.
- Keep `agent.dev_random_seed: false` (as `examples/hermes-stdio.yaml` does) so the bridge address stays stable; `doctor` and `serve` warn if a config ignores `UAGENT_SEED`.
- Keep `policy.public_tools` empty or small, and read the JSONL audit log: alert on spikes in denials, replay rejections, `backend unavailable` errors, and send failures.
- With `publish_manifest: false` the bridge is not in the Almanac, so only clients configured with its endpoint can reach it. With `publish_manifest: true`, uAgents registers it on the Almanac contract, which can spend registration fees from the wallet derived from `UAGENT_SEED`. Neither public discovery path is covered by CI yet.

Deployment notes, including a systemd unit, are in [`docs/production.md`](docs/production.md); every setting and its default is in [`docs/configuration.md`](docs/configuration.md).

## Roadmap

- [ ] Release `v1.0.0` and publish to PyPI.
- [x] Catalog-ready Hermes plugin ([`hermes-plugin/fetchai-bridge`](hermes-plugin/fetchai-bridge)), checked against real Hermes in CI.
- [ ] Submit the `plugin-catalog` entry to hermes-agent. Draft and steps: [`docs/upstream-hermes-pr.md`](docs/upstream-hermes-pr.md).
- [ ] Verify the Agentverse mailbox tier and Almanac registration end to end on testnet.
- [ ] Support mcp 2.x and Python 3.13+, so the in-process mode also works with current Hermes.
- [ ] Drop the PyNaCl and ecdsa dependency-audit exceptions once upstream allows (see [`docs/security.md`](docs/security.md)).
- [ ] Sell services you define to other agents for FET, with each payment verified on the ledger (testnet).
- [ ] Reach Hermes from ASI:One in plain language, with ASI:One's testnet payment card.
- [ ] Let Hermes find and pay other agents, asking you before every payment.
- [ ] Guided setup (`hermes fetchai-bridge setup`) and plain-language docs.

## Documentation

| Doc | Covers |
|-----|--------|
| [`docs/architecture.md`](docs/architecture.md) | Message flow, trust boundaries, design decisions, failure behavior |
| [`docs/configuration.md`](docs/configuration.md) | Every config setting and its default |
| [`docs/demo.md`](docs/demo.md) | Local demo, Hermes-backed demo, client call shape, field test |
| [`docs/production.md`](docs/production.md) | Secrets, systemd, the replay-protection contract, network egress, monitoring |
| [`docs/security.md`](docs/security.md) | Threat model, controls, residual risks |
| [`docs/troubleshooting.md`](docs/troubleshooting.md) | Error messages and what to do about them |
| [`docs/agentverse-mailbox.md`](docs/agentverse-mailbox.md) | Manual Agentverse mailbox setup (unverified) |
| [`docs/hermes-plugin.md`](docs/hermes-plugin.md) | The `fetchai-bridge` Hermes plugin: install, settings, how it runs the bridge |
| [`docs/upstream-hermes-pr.md`](docs/upstream-hermes-pr.md) | Plan and ready-to-paste text for the Hermes plugin catalog |
| [`docs/agent-economy.md`](docs/agent-economy.md) | Design and status of selling and buying services between agents (in development) |

## Development

- License: MIT. Supported Python: 3.11 and 3.12.
- The local gate is in [`CONTRIBUTING.md`](CONTRIBUTING.md): ruff (lint and format), mypy (strict for the package), and pytest with a 90% branch-coverage floor, among others. The test suite runs offline.
- CI also runs the tests on Linux, macOS, and Windows with Python 3.11 and 3.12, installs the built wheel, runs the Hermes plugin checks and stdio field test against real Hermes, audits dependencies, and runs CodeQL. Dependabot proposes updates. Ruff and mypy are pinned to a minor series so tool releases cannot change the rules underneath CI.

## Scope

This package is a connection layer, not an agent framework. It is growing into a way for Hermes to take part in Fetch.ai's agent economy: selling services you define to other agents and to ASI:One users, and paying other agents with your approval. Payments run on Fetch's testnet only (test tokens with no value) until a security review; see the [design](docs/agent-economy.md) and the roadmap.
