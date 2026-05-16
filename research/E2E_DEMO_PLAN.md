# E2E Demo Plan

Date accessed: 2026-05-16

## Demo goals

Prove three levels separately:

1. Local deterministic demo: local uAgent client -> Hermes Fetch AI bridge -> fake MCP/Hermes MCP -> response.
2. Hermes-backed demo: local uAgent client -> bridge -> Hermes MCP or Hermes tools FastMCP -> response.
3. Agentverse demo: Agentverse/Mailbox or public endpoint -> bridge -> Hermes -> response.

The demo must be narrow, reproducible, and safe. It must not require payments, billing, marketplace pricing, wallet UX beyond seed identity, domain-specific examples, or broad tool exposure.

## Demo 1: local deterministic direct protocol

Purpose: CI-grade proof with no hosted dependencies.

Setup:

- `UAGENT_SEED=dev-only-stable-seed-do-not-use-in-prod`
- bridge port `8000`, client port `8001`
- endpoint `http://127.0.0.1:8000/submit`
- fake MCP echo server or in-process FastMCP object

Expected commands:

```bash
python -m hermes_fetch_ai.examples.fake_mcp_bridge --port 8000
python -m hermes_fetch_ai.examples.local_client --bridge http://127.0.0.1:8000/submit --action list-tools
python -m hermes_fetch_ai.examples.local_client --bridge http://127.0.0.1:8000/submit --action call-tool --tool echo --args '{"text":"hello"}'
```

Expected logs:

- bridge prints uAgent address.
- bridge prints endpoint binding.
- bridge logs policy-aware direct protocol included with manifest publication flag.
- client logs request envelope sent and response received.
- audit log records `allow` decision for `echo`, sender address, and redacted/truncated payload.

Success criteria:

- `ListTools` returns `echo`.
- `CallTool` returns `hello`.
- No ASI key, Agentverse login, or public endpoint is required.
- No secrets appear in logs.

## Demo 2: Hermes-backed local proof

Purpose: prove the Hermes side of the bridge.

Preferred path:

```bash
hermes mcp serve --verbose
```

Then the bridge starts `HermesMCPClientShim(command="hermes", args=["mcp", "serve"])` or starts it internally.

Fallback path:

```python
from agent.transports.hermes_tools_mcp_server import _build_server
mcp = _build_server()
```

Expected commands:

```bash
python -m hermes_fetch_ai.bridge --config examples/local-hermes.yaml
python -m hermes_fetch_ai.examples.local_client --action list-tools
python -m hermes_fetch_ai.examples.local_client --action call-tool --tool skills_list --args '{}'
```

Use the safest available tool. If `skills_list` or another read-only tool is unavailable, use a purpose-built fake MCP server until Hermes package issue is resolved.

Success criteria:

- Bridge lists only policy-allowed Hermes tools.
- Calling a read-only allowed tool succeeds.
- Calling a disabled or side-effecting tool returns a policy denial before reaching Hermes.
- Audit log has redacted input/output and no raw secrets.

## Demo 3: Agentverse Mailbox / CEO demo

Purpose: prove Fetch public network UX without requiring public inbound networking.

Prerequisites:

- Stable seed from environment, never committed.
- Agentverse login/Inspector flow.
- Optional `ASI1_API_KEY` only if using chat protocol.
- Demo config sets `mailbox: true`.

Expected commands:

```bash
export UAGENT_SEED='...'
export ASI1_API_KEY='...'        # only for chat demo
python -m hermes_fetch_ai.bridge --config examples/agentverse-mailbox.yaml
```

Expected behavior:

- Bridge prints Agent Inspector URL.
- Operator links mailbox through Agentverse/Inspector.
- Agent details show name, description, readme/profile, and protocol manifest.
- A remote direct uAgent or Agentverse chat sends a request.
- Bridge returns a read-only, bounded Hermes response.

Success criteria:

- Agent is discoverable/reachable through Agentverse/Mailbox.
- Response completes within configured timeout.
- Unknown sender/tool policy behaves as documented.
- No raw seed/token/API key appears in logs or docs.

## Demo 4: production-ish public endpoint

Purpose: optional later proof for always-on deployment.

Requirements:

- Public HTTPS endpoint ending in `/submit`.
- Stable seed in environment/secret manager.
- Explicit allowed sender/tool policy.
- rate limits and timeouts.
- log retention settings.
- health check endpoint if included.

Deferred until local and mailbox demos pass.

## Failure modes to test

- Unknown sender attempts allowed public tool: allowed only if tool policy says public.
- Unknown sender attempts non-public/admin tool: denied.
- Known sender sends malformed args: schema/policy error.
- Tool output exceeds cap: truncated/summarized with audit marker.
- MCP server not running: bridge returns structured unavailable error.
- MCP call timeout: bridge cancels and returns timeout error.
- uAgent seed missing: bridge refuses to start except in explicit dev mode.
- ASI key missing: direct protocol still works; chat protocol disabled with clear message.
- Agentverse unavailable: local direct endpoint still works.

## Message-flow sequence

```text
Remote uAgent/Agentverse
  -> uAgents envelope to bridge address/endpoint/mailbox
  -> Hermes Fetch AI uAgent runtime
  -> policy-aware direct MCP protocol (`ListTools` / `CallTool`)
  -> Bridge policy layer (sender/tool/schema/rate/timeout/logging)
  -> HermesMCPClientShim
  -> Hermes MCP server or fake MCP test server
  -> Response normalization
  -> uAgent response envelope
  -> Remote sender
```

## Demo script narrative

Safe public story:

"Hermes supplies the local agent and execution environment. Fetch supplies identity, addressing, discovery, and agent-to-agent rails. Hermes Fetch AI connects them through MCP with a small policy layer. Agentverse discovery is identity and routing, not trust; tool execution remains local and allowlisted."
