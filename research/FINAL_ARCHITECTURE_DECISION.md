# Final Architecture Decision
Date accessed: 2026-05-16
Status: supersedes `research/HARDENED_ARCHITECTURE_DECISION.md`.

## Final architecture

Hermes Fetch AI v1 is a standalone Python package that exposes a narrow, policy-aware MCP-over-uAgents bridge.

The bridge owns exactly one uAgent protocol for v1:

- `Protocol(spec=mcp_protocol_spec, role="server")`
- message models imported from `uagents_adapter.mcp.protocol`:
  - `ListTools`
  - `ListToolsResponse`
  - `CallTool`
  - `CallToolResponse`
  - `mcp_protocol_spec`

The bridge never publishes `MCPServerAdapter.protocols`, never publishes the adapter chat protocol, and never treats `MCPServerAdapter` as the security boundary. The adapter is source evidence and a provider of message-model/wire compatibility only.

The runtime layers are:

1. Fetch/uAgents layer: identity, address, signed envelopes, dispatch, endpoint/mailbox/proxy modes, optional Almanac/Agentverse rails.
2. Bridge layer: config, policy, sender-filtered inventory, arg validation, rate limits, result normalization, redacted audit logs, CLI/docs/tests.
3. MCP/Hermes layer: fake MCP server for CI, `_build_server()` for a Hermes-backed local demo, stdio/SSE/HTTP MCP client transports for future/manual modes.
4. Hermes local execution: Hermes owns tools, MCP, redaction conventions, config, and execution boundaries.

## Why existing rails are enough

Fetch/uAgents already provide:

- cryptographic agent identity and addresses;
- signed envelope routing;
- in-process dispatcher for deterministic local two-agent tests;
- endpoint, mailbox, and proxy modes;
- optional Agentverse/Almanac discovery and manifests;
- `Protocol(spec=..., role="server")` role binding;
- published MCP protocol message models/spec via `uagents_adapter.mcp.protocol`.

MCP already provides:

- `ClientSession.list_tools()` returning `ListToolsResult`;
- `ClientSession.call_tool()` returning `CallToolResult`;
- stdio, SSE, and streamable HTTP client transports;
- stable v1 `mcp.server.fastmcp.FastMCP` under the exact v1 pin.

Hermes already provides:

- local tool registry and dispatch;
- optional MCP extras;
- `agent.transports.hermes_tools_mcp_server._build_server()` for a local FastMCP-backed demo surface;
- redaction/logging conventions;
- MCP client subprocess hardening patterns.

Therefore this repo does not need a new agent framework, new marketplace, new identity system, new discovery layer, chat implementation, wallet UX, payment layer, or commercial skill manifest. It needs only the missing trust-boundary glue.

## Exact thin layer this repo adds

Package: `hermes-fetch-ai`.

Modules:

- `config.py`: versioned YAML/env config; rejects unknown fields, secret-shaped YAML values, and `chat.enable_chat=true`; supports `dev_random_seed` for local demos.
- `policy.py`: pure default-deny policy, sender/tool allowlists, denylist override, per-sender rate limits for `ListTools` and `CallTool`.
- `arg_validator.py`: JSON schema validation and URL/SSRF guards before tool invocation.
- `result_normalizer.py`: normalizes both client-side `mcp.types.CallToolResult` and server-side/in-process FastMCP result shapes into `NormalizedToolResult`.
- `mcp_shim.py`: owns MCP lifecycle for fake, in-process Hermes tools, stdio, SSE, and HTTP modes; never passed to `MCPServerAdapter`.
- `fake_mcp.py`: internal fake FastMCP builder for CI/local demo; examples import this, not vice versa.
- `direct_protocol.py`: builds the bridge-owned signed-message protocol and handlers.
- `uagent_app.py`: constructs `uagents.Agent`, includes only the bridge protocol, and applies CI-safe registration/manifest/inspector defaults.
- `registration_policies.py`: `NoopRegistrationPolicy` for offline CI.
- `_redaction.py`, `logging.py`, `audit.py`: redacted logs and JSONL audit without raw args/outputs/secrets.
- `hermes_probe.py`: probes Hermes local availability and reports the `mcp_serve.py` packaging blocker distinctly.
- `cli.py`: `doctor`, `probe-hermes`, `serve`, `demo local`, `demo mailbox`.
- `version_pins.py`: exact version expectations.

## Exact message flow

### Local CI flow

1. Test/demo creates a bridge agent and client agent in the same Python process.
2. Both agents use `network="testnet"`, `NoopRegistrationPolicy`, `enable_agent_inspector=False`, and `publish_manifest=False`.
3. Both register with the module-level uAgents dispatcher on construction.
4. Bridge starts `HermesMCPClientShim(mode="fake")`, backed by `src/hermes_fetch_ai/fake_mcp.py`.
5. Bridge builds `direct_protocol.build_protocol(...)` and includes it on the bridge agent.
6. Client sends `ListTools` to bridge address.
7. uAgents routes through in-process dispatcher; no hosted service is required for the assertion path.
8. Bridge signed handler receives `(ctx, sender, msg)`.
9. Handler rate-limits sender, calls `shim.list_tools()`, filters with `policy.visible_tools(sender, tools, cfg.policy)`, caps serialized response size, audits, and sends `ListToolsResponse`.
10. Client sends `CallTool(tool="echo", args={"text":"hello"})`.
11. Bridge checks args byte size, rate limit, authorization, tool existence, JSON schema, SSRF guards, and only then calls shim.
12. Shim returns `NormalizedToolResult`.
13. Handler audits output bytes/truncation/error status and sends `CallToolResponse`.

### Hermes-backed local demo flow

1. Operator installs Hermes with MCP extras and runs `python -m hermes_fetch_ai.cli probe-hermes`.
2. Config uses `hermes_mcp.mode: in_process_hermes_tools`.
3. Shim lazy-imports `agent.transports.hermes_tools_mcp_server._build_server()`.
4. Policy sets demo public tools to `skills_list` only; all other known `EXPOSED_TOOLS` are denylisted.
5. A local client calls `skills_list`; side-effecting tools return structured deny responses.

### Agentverse/manual demo flow

1. Operator sets `UAGENT_SEED` outside the repo.
2. Operator runs `python -m hermes_fetch_ai.cli demo mailbox` or `serve --config examples/agentverse-mailbox.yaml`.
3. Config uses testnet, mailbox mode, and explicit manifest/inspector opt-in.
4. Operator links mailbox in Agentverse UI.
5. Remote uAgent sends `ListTools`/`CallTool` using the same MCP protocol messages.
6. The exact same bridge policy path handles the request.

## Exact trust boundaries

Boundary 1: remote uAgent to uAgents runtime.

- uAgents verifies signed envelopes for signed handlers.
- Sender address is authenticated routing identity only.
- Sender address is never sufficient authorization.

Boundary 2: uAgents runtime to bridge policy handlers.

- Only signed `on_message` handlers are used.
- No `on_query` path for bridge protocol.
- `ListTools` and `CallTool` are both authorization surfaces.
- Unknown senders get only configured public tools or an empty list.

Boundary 3: bridge policy to MCP shim.

- Denied calls never invoke the shim.
- Args are size-checked and schema-validated before shim call.
- URL-like args are SSRF-checked before shim call.
- Per-sender rate limits apply before expensive operations.

Boundary 4: MCP shim to Hermes/local subprocess.

- Stdio uses `shell=False`, static command/args from config, filtered env, timeout, and stderr redirection.
- Windows preserves required process env vars but no secrets by default.
- Output is normalized and truncated before returning across uAgents.

Boundary 5: logs/audit.

- Audit records decisions, sizes, truncation, durations, and error classes.
- Audit never records raw args, raw outputs, seeds, tokens, API keys, prompts, or full sender addresses.

## Exact local CI path

Commands:

```text
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows PowerShell
# . .venv/bin/activate              # POSIX
python -m pip install -U pip
python -m pip install -e ".[dev]"
python -m hermes_fetch_ai.cli doctor
python -m pytest -q
python -m hermes_fetch_ai.cli demo local
```

CI requirements:

- Python 3.11 or 3.12 only.
- No Agentverse, Almanac, ASI key, hosted endpoint, real Hermes install, real mailbox token, or internet dependency for unit suite.
- In-process two-agent dispatcher proves request/response behavior.
- Baseline doctor validates local-direct config with `dev_random_seed=true`; it does not require `UAGENT_SEED`.
- `tests/test_contamination.py` passes.

## Exact Hermes-backed demo path

Commands:

```text
python -m hermes_fetch_ai.cli probe-hermes
python -m hermes_fetch_ai.cli serve --config examples/hermes-local.yaml
python examples/local_client.py --bridge <bridge-address> --tool skills_list --args "{}"
```

Expected behavior:

- `_build_server()` path is reported as usable by `probe-hermes`, or the demo stops with actionable install/config hints.
- `skills_list` returns local skill metadata if Hermes is available.
- All other Hermes tools are denied unless explicitly configured.
- `skill_view` is not demo-public by default because it can reveal private skill content.
- Operators may set public tools to empty for maximum privacy.

## Exact Agentverse/manual demo path

Commands:

```text
$env:UAGENT_SEED = "..."             # PowerShell; do not commit
python -m hermes_fetch_ai.cli demo mailbox
```

Or POSIX:

```text
export UAGENT_SEED="..."
python -m hermes_fetch_ai.cli demo mailbox
```

Manual requirements:

- Real seed in env, never in YAML or repo.
- Testnet default unless operator explicitly opts into mainnet.
- Mailbox/Inspector linking is manual and outside CI.
- No chat protocol in v1.
- No ASI key required.

## Dependency pins

Final v1 reproducibility pins:

- `uagents==0.24.2`
- `uagents-core==0.4.4`
- `uagents-adapter[mcp]==0.6.2`
- `mcp==1.27.1`
- `pydantic>=2.8,<3`
- `PyYAML>=6,<7`
- `python-dotenv>=1.0,<2`
- `jsonschema>=4.20,<5`
- `httpx>=0.25,<1`
- dev: `pytest>=8,<9`, `pytest-asyncio>=0.23,<1`, `anyio>=4,<5`, `ruff>=0.5`, `mypy>=1.10`

## Final confidence level

- Local CI fake-MCP direct uAgent demo: green.
- Hermes-backed local demo via `_build_server()` and `skills_list`: yellow-green.
- Agentverse mailbox/manual demo: yellow.
- `hermes mcp serve` stdio path: red until Hermes publishes a working `mcp_serve.py` path.
- Upstream Hermes PR shape: yellow; CLI/plugin is recommended, platform adapter remains fallback only by maintainer request.

## Final decision

Proceed with autonomous implementation using `research/FINAL_BUILD_PROMPT.md`. Stop immediately if implementation evidence contradicts these boundaries, if CI would require hosted services, if `MCPServerAdapter.protocols` or chat is needed to make progress, or if a safety test would need to be skipped.
