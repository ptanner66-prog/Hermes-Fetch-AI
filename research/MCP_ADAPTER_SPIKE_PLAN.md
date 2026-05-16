# MCP Adapter Spike Plan

Date accessed: 2026-05-16

## Goal

Prove whether Hermes can be exposed as a Fetch.ai uAgent through existing `uagents-adapter` and MCP rails with only a thin Hermes-specific bridge layer. The rail exists, but adversarial review found the unmodified adapter is not a safe v1 security boundary because direct handlers receive `sender` and then call `self.mcp.list_tools()` / `self.mcp.call_tool(...)` without passing sender into the MCP object.

## Revised hypothesis

`uagents-adapter==0.6.2` is sufficient as evidence and reference implementation for MCP-shaped uAgent messages, but v1 should publish a bridge-owned policy-aware direct protocol by default. The bridge still remains thin:

```python
async def list_tools(self): ...
async def call_tool(self, name: str, args: dict): ...
```

A raw `hermes mcp serve` process is not sufficient because `MCPServerAdapter` does not accept command/args/URL transport configuration. A sender-blind shim is also not sufficient because authorization and sender-filtered tool inventory must happen before MCP access.

## Spike A: message-model and local uAgent direct proof

Objective: prove the bridge can reuse/import direct MCP message shapes while owning policy-aware handlers.

Steps:

1. Create virtualenv with pins:
   - `python>=3.11`
   - `uagents==0.24.2`
   - `uagents-core==0.4.4`
   - `uagents-adapter==0.6.2`
   - `mcp==1.27.1`
2. Import or copy-with-attribution the direct protocol model shapes: `ListTools`, `ListToolsResponse`, `CallTool`, `CallToolResponse`.
3. Build a tiny `uagents.Protocol` in `src/hermes_fetch_ai/direct_protocol.py`.
4. Handlers must receive `sender` and call policy before shim/MCP access.
5. Use fake in-process MCP object with one `echo(text: str) -> str` tool.
6. Run two local uAgents: bridge and client. Client sends `ListTools` and `CallTool` messages.

Success:

- Unknown sender `ListTools` returns only public-safe `echo` or an empty list, depending config.
- Unknown sender cannot see non-public fake tools.
- Allowed sender receives allowed tool list and `echo` result.
- Denied `CallTool` never invokes fake MCP object.
- No ASI key is needed for direct `ListTools`/`CallTool`.

Failure interpretation:

- If message models fail: copy minimal Pydantic/uAgents models locally with source links.
- If local two-agent send fails: isolate uAgents endpoint/resolver mechanics before touching Hermes.
- If only chat fails: not blocking v1 direct protocol.

## Spike B: verify `hermes mcp serve`

Objective: prove the package CLI starts and can be queried by an MCP client.

Steps:

1. Create clean virtualenv.
2. Install `hermes-agent==0.13.0` and `mcp==1.27.1` or `mcp==1.26.0` if needed.
3. Run:
   `python -m hermes_cli.main mcp serve --verbose`
   or the installed console script:
   `hermes mcp serve --verbose`.
4. Capture stdout/stderr separately; MCP protocol must use stdio cleanly.
5. Use official MCP SDK stdio client:
   - `StdioServerParameters(command="hermes", args=["mcp", "serve", "--verbose"])`
   - `stdio_client(...)`
   - `ClientSession(...).initialize()`
   - `session.list_tools()`
   - call one harmless tool if listed.
6. If import fails with `mcp_serve` missing, document as Hermes packaging blocker and switch to Spike C/D.

Success:

- Stdio client can initialize and list Hermes MCP tools/conversation operations.

Failure:

- `ModuleNotFoundError: mcp_serve`, MCP version incompatibility, or dirty stdout is a direct blocker for process wrapping. Fake-MCP bridge coding can continue.

## Spike C: HermesMCPClientShim over stdio

Objective: convert a stdio MCP process into the in-process method shape expected by the bridge-owned direct protocol.

Minimal class responsibilities:

- lazy start or explicit `start()` of MCP stdio session;
- `async list_tools()` returns `result.tools` from `ClientSession.list_tools()`;
- `async call_tool(name, args)` calls `ClientSession.call_tool(name, args or {})`;
- normalize `TextContent`, `ImageContent`, structured content, and error flags into deterministic string/JSON;
- `close()` tears down session cleanly;
- per-call timeout and bounded reconnect after broken pipe;
- redacted logs only.

Tests:

1. Use fake MCP server fixture from Spike A, started as subprocess.
2. Assert `shim.list_tools()` returns tool objects with `.name`, `.description`, `.inputSchema`/schema properties usable by direct protocol responses.
3. Assert `shim.call_tool()` normalizes output.
4. Inject server crash; assert clean error and reconnect behavior if enabled.
5. Pass shim into policy-aware direct protocol and run local direct uAgent test.

Success:

- Bridge can list and call MCP tools through a stdio shim after policy allows.

Failure:

- If event-loop/threading conflicts with uAgents runtime, add a bounded worker/queue around shim calls; do not bypass policy.

## Spike D: in-process Hermes FastMCP fallback

Objective: prove the existing Hermes FastMCP builder can be queried by the bridge-owned protocol when `hermes mcp serve` is blocked.

Steps:

1. Install `hermes-agent==0.13.0` plus `mcp`.
2. Import `agent.transports.hermes_tools_mcp_server._build_server`.
3. Call `_build_server()` and inspect `await server.list_tools()`.
4. Call one safe tool through the bridge policy layer if available.
5. Run local direct uAgent `ListTools`/`CallTool` against a safe tool such as `skills_list` if available and safe.

Caveats:

- This server is designed for Codex subprocess use and exposes a curated tools subset, not necessarily full Hermes conversations.
- It may import user config and tool availability checks; run in a test profile to avoid surprising local state.

Success:

- Fastest demo path if `hermes mcp serve` is blocked.

Failure:

- Not fatal if Spike C works with a fake server; it just means the bridge needs Hermes CLI/source issue resolved before a Hermes-specific demo.

## Spike E: optional adapter/chat demo

Objective: prove optional Agentverse/ASI chat UX after local direct protocol passes.

Steps:

1. Set `UAGENT_SEED` and optionally `AGENTVERSE_TOKEN`/Inspector flow according to docs.
2. Run bridge with `mailbox=True`.
3. Publish policy-aware direct protocol with `publish_manifest=True`.
4. Do not publish chat unless `chat.enable_chat: true`, `ASI1_API_KEY` is present, redacted logging is configured, and timeouts are set.
5. If using chat demo, send a prompt that should call only a read-only allowed tool.
6. Enforce bridge policy after model tool selection and before MCP invocation.
7. Verify response and audit log.

Success:

- Agent appears in Agentverse/Inspector.
- Direct protocol reaches Hermes-backed tool.
- Optional chat, if enabled, does not leak raw prompts/tool payloads in logs and cannot bypass policy.

## Stop/go criteria

Go with bridge-owned direct protocol + shim if Spikes A and C pass, even if B is blocked.

Go with in-process fallback if A and D pass and B/C are blocked, but document reduced scope.

Only fork/subclass `MCPServerAdapter` if it can pass sender into policy before `list_tools`/`call_tool`, suppress raw logging, and publish direct protocol without chat by default.

Do not use unmodified `MCPServerAdapter.protocols` for production/security tests unless explicitly proving why the sender-blind path is safe for a fake/public-only demo.

## Exact next unresolved command

The first build run should start with:

```bash
python -m venv .venv
. .venv/Scripts/activate 2>/dev/null || . .venv/bin/activate
python -m pip install -U pip
python -m pip install uagents==0.24.2 uagents-core==0.4.4 uagents-adapter==0.6.2 mcp==1.27.1 pytest pytest-asyncio pydantic python-dotenv
python - <<'PY'
from uagents import Agent, Protocol
from uagents_adapter.mcp import ListTools, CallTool
from mcp.server.fastmcp import FastMCP
print('imports ok')
PY
```
