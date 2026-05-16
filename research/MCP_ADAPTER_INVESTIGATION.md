# MCP adapter/source investigation

> Hardened note (2026-05-16): For final v1 decisions, see `research/HARDENED_ARCHITECTURE_DECISION.md`, `research/HARDENED_BUILD_PROMPT.md`, and `research/HARDENING_AUDIT.md`. Where this file disagrees with the hardened deliverables, the hardened deliverables are authoritative.

Date accessed: 2026-05-16
Workspace: C:\Users\ptann\OneDrive\Work\Hermes Fetch AI

## Bottom line

`uagents-adapter` 0.6.2 does not wrap arbitrary external MCP endpoints directly. Its `MCPServerAdapter` expects an in-process Python object with the FastMCP-style async methods `list_tools()` and `call_tool(name, args)`, plus a synchronous `run(transport=...)` method. The package docs show importing `mcp` from a local `server.py`, not connecting to a stdio subprocess, SSE URL, or streamable HTTP URL.

Therefore, a direct wrap of `hermes mcp serve` as a separate stdio process is not supported by the current adapter shape. Best v1 path is either:

1. preferred shim: create a small Python wrapper object that uses MCP Python SDK client transports to connect to Hermes' MCP server over stdio or HTTP, and exposes `list_tools`, `call_tool`, and a no-op/safe `run`; then pass that object to `MCPServerAdapter`; or
2. deeper integration: import/build Hermes' FastMCP server object in-process and pass that to `MCPServerAdapter`, if Hermes exposes a stable builder. This is less safe until the Hermes server module/import lifecycle is proven.

## Source-backed findings

### uagents-adapter package and source

Package/version:
- PyPI package: `uagents-adapter` 0.6.2, public URL: https://pypi.org/project/uagents-adapter/0.6.2/
- Source inspected from public Fetch.ai repo clone: https://github.com/fetchai/uAgents, commit `6d7008971eaff74e0a0ca564c19d666f5047ef1a`
- Source path: `python/uagents-adapter`
- `pyproject.toml` declares version 0.6.2 and optional MCP dependency `mcp (>=1.8.1)` under `[project.optional-dependencies].mcp`: https://github.com/fetchai/uAgents/blob/6d7008971eaff74e0a0ca564c19d666f5047ef1a/python/uagents-adapter/pyproject.toml#L1-L47

Adapter shape:
- `MCPServerAdapter.__init__(mcp_server, asi1_api_key, model, asi1_base_url=...)` just stores the object as `self.mcp`; there is no URL/command/client transport parameter: https://github.com/fetchai/uAgents/blob/6d7008971eaff74e0a0ca564c19d666f5047ef1a/python/uagents-adapter/src/uagents_adapter/mcp/adapter.py#L41-L64
- For uAgent MCP protocol `ListTools`, it executes `tools = await self.mcp.list_tools()` and serializes each tool's `name`, `description`, and `inputSchema`: https://github.com/fetchai/uAgents/blob/6d7008971eaff74e0a0ca564c19d666f5047ef1a/python/uagents-adapter/src/uagents_adapter/mcp/adapter.py#L81-L105
- For uAgent MCP protocol `CallTool`, it executes `output = await self.mcp.call_tool(msg.tool, msg.args)`: https://github.com/fetchai/uAgents/blob/6d7008971eaff74e0a0ca564c19d666f5047ef1a/python/uagents-adapter/src/uagents_adapter/mcp/adapter.py#L107-L121
- For Chat Protocol, it again calls `await self.mcp.list_tools()` and converts each tool to an OpenAI/ASI-style function tool with `parameters = tool.inputSchema`: https://github.com/fetchai/uAgents/blob/6d7008971eaff74e0a0ca564c19d666f5047ef1a/python/uagents-adapter/src/uagents_adapter/mcp/adapter.py#L177-L198
- On model tool calls, it calls `await self.mcp.call_tool(selected_tool, tool_args)`: https://github.com/fetchai/uAgents/blob/6d7008971eaff74e0a0ca564c19d666f5047ef1a/python/uagents-adapter/src/uagents_adapter/mcp/adapter.py#L266-L323
- `run(agent)` starts the uAgent in a daemon thread, then calls `self.mcp.run(transport="stdio")`: https://github.com/fetchai/uAgents/blob/6d7008971eaff74e0a0ca564c19d666f5047ef1a/python/uagents-adapter/src/uagents_adapter/mcp/adapter.py#L413-L426

Docs/examples:
- README says MCP support lets MCP servers be hosted/discovered through Agentverse/ASI:One and says to create a FastMCP server exposing `list_tools` and `call_tool`, then import the `mcp` server instance: https://github.com/fetchai/uAgents/blob/6d7008971eaff74e0a0ca564c19d666f5047ef1a/python/uagents-adapter/README.md#L164-L193
- MCP README usage says the two components are: creating a FastMCP server and setting up a uAgent using `MCPServerAdapter`; example imports `from server import mcp`: https://github.com/fetchai/uAgents/blob/6d7008971eaff74e0a0ca564c19d666f5047ef1a/python/uagents-adapter/src/uagents_adapter/mcp/README.md#L20-L135

Conclusion for transport support:
- FastMCP in-process object: supported if it has the official MCP SDK FastMCP methods and `run()`.
- stdio MCP subprocess: not directly supported by `MCPServerAdapter`; requires a client shim object.
- SSE MCP endpoint: not directly supported; requires a client shim object.
- HTTP/streamable MCP endpoint: not directly supported; requires a client shim object.
- Arbitrary MCP server object: only supported if it mimics the required in-process shape: async `list_tools`, async `call_tool`, and `run(transport="stdio")`.

### MCP Python SDK / official FastMCP support

Package/version:
- PyPI package: `mcp` 1.27.1, public URL: https://pypi.org/project/mcp/1.27.1/
- Project URLs: https://modelcontextprotocol.io and https://github.com/modelcontextprotocol/python-sdk
- Source inspected from repo commit `161834d4aee2633c42d3976c8f8751b6c4d947d5`

FastMCP server API:
- Official SDK includes `mcp.server.fastmcp.FastMCP`: https://github.com/modelcontextprotocol/python-sdk/blob/main/src/mcp/server/fastmcp/server.py
- `FastMCP.run()` accepts `transport: Literal["stdio", "sse", "streamable-http"] = "stdio"`: https://github.com/modelcontextprotocol/python-sdk/blob/161834d4aee2633c42d3976c8f8751b6c4d947d5/src/mcp/server/fastmcp/server.py#L279-L300
- `FastMCP.list_tools()` returns MCP tool objects with `name`, `description`, `inputSchema`, etc.: https://github.com/modelcontextprotocol/python-sdk/blob/161834d4aee2633c42d3976c8f8751b6c4d947d5/src/mcp/server/fastmcp/server.py#L315-L330
- `FastMCP.call_tool(name, arguments)` exists and dispatches through the tool manager: https://github.com/modelcontextprotocol/python-sdk/blob/161834d4aee2633c42d3976c8f8751b6c4d947d5/src/mcp/server/fastmcp/server.py#L343-L346
- The SDK has server runners for stdio, SSE, and streamable HTTP: stdio at lines 753-760, SSE at 762-775, streamable HTTP at 777-790: https://github.com/modelcontextprotocol/python-sdk/blob/161834d4aee2633c42d3976c8f8751b6c4d947d5/src/mcp/server/fastmcp/server.py#L753-L790
- It exposes SSE and streamable HTTP Starlette apps: https://github.com/modelcontextprotocol/python-sdk/blob/161834d4aee2633c42d3976c8f8751b6c4d947d5/src/mcp/server/fastmcp/server.py#L818-L948 and https://github.com/modelcontextprotocol/python-sdk/blob/161834d4aee2633c42d3976c8f8751b6c4d947d5/src/mcp/server/fastmcp/server.py#L950-L1045

Implication:
- `uagents-adapter` aligns with the official SDK's in-process `FastMCP` object, not with MCP wire transports as client connections.

### Standalone FastMCP package

Package/version:
- PyPI package: `fastmcp` 3.3.1, public URL: https://pypi.org/project/fastmcp/3.3.1/
- Public docs: https://gofastmcp.com
- Public repo: https://github.com/PrefectHQ/fastmcp, inspected commit `d8dcc273cac9f6f17889a1b60adbdc654f948a50`

Finding:
- The standalone package is a separate actively maintained project. Its metadata says FastMCP 1.0 was incorporated into the official MCP Python SDK, while current FastMCP is maintained as standalone; PyPI package `fastmcp` 3.3.1 depends on `fastmcp-slim[client,server]==3.3.1`.
- `uagents-adapter` imports/examples use `from mcp.server.fastmcp import FastMCP`, not `from fastmcp import FastMCP`.

Risk:
- Do not assume standalone `fastmcp.FastMCP` 3.x has exactly the same runtime methods/return types as `mcp.server.fastmcp.FastMCP`; test explicitly before using it with `MCPServerAdapter`.

### Hermes MCP surface relevant to direct wrapping

Package/version:
- PyPI package: `hermes-agent` 0.13.0, public URL: https://pypi.org/project/hermes-agent/0.13.0/
- The PyPI wheel was inspected locally. Metadata shows version 0.13.0 and `mcp==1.26.0` only in the `dev` extra, not as a base dependency.

Hermes MCP server:
- `hermes_cli/main.py` defines `hermes mcp serve` with help text "Run Hermes as an MCP server (expose conversations to other agents)": local wheel reference `research/pkgs/src/hermes_agent-0.13.0-py3-none-any/hermes_cli/main.py:11107-11129`.
- `hermes_cli/mcp_config.py` dispatches action `serve` to `from mcp_serve import run_mcp_server`: local wheel reference `research/pkgs/src/hermes_agent-0.13.0-py3-none-any/hermes_cli/mcp_config.py:749-756`.
- The wheel I inspected did not contain a top-level `mcp_serve.py` file. This may be a packaging omission, namespace/import issue, or an artifact of the wheel layout. This is a blocking verification item before assuming `hermes mcp serve` works from PyPI 0.13.0.

Hermes tools-as-MCP server:
- Hermes also includes `agent/transports/hermes_tools_mcp_server.py`, which builds an in-process `mcp.server.fastmcp.FastMCP` server named `hermes-tools` and exposes a curated subset of Hermes tools. It returns the server object from `_build_server()` and runs it with default stdio from `main()`: local wheel references `agent/transports/hermes_tools_mcp_server.py:100-117`, `:117-186`, `:189-215`.
- This module is designed for Codex subprocess use, not necessarily for exposing full Hermes conversations. It may be a useful spike target because `_build_server()` returns an actual FastMCP object that matches the adapter shape.

Hermes outbound MCP client:
- `hermes mcp add` supports `--url` for HTTP/SSE endpoints and `--command`/`--args` for stdio servers: local wheel reference `hermes_cli/main.py:11131-11155`.
- This confirms Hermes consumes MCP over stdio/URL, but does not make `uagents-adapter` consume those transports directly.

## Compatibility matrix

| Source shape | Supported by uagents-adapter 0.6.2 directly? | Evidence / notes |
|---|---:|---|
| Official SDK in-process `mcp.server.fastmcp.FastMCP` | Yes | Has `list_tools`, `call_tool`, `run`; adapter docs use it. |
| Custom in-process object with async `list_tools`, async `call_tool`, and `run` | Likely yes | Adapter is duck-typed; no type check. |
| stdio MCP server command/process | No | Adapter has no command/args client config; it calls methods on object. Needs shim. |
| SSE MCP URL | No | Adapter has no URL/session/client config. Needs shim. |
| streamable HTTP MCP URL | No | Adapter has no URL/session/client config. Needs shim. |
| Standalone `fastmcp.FastMCP` 3.x | Unknown / test required | Separate package; not the import used by uagents-adapter docs. |
| `hermes mcp serve` CLI process | No, not directly | It is a stdio/server process shape; adapter needs object methods. |
| Hermes `agent.transports.hermes_tools_mcp_server._build_server()` | Potentially yes | Returns official SDK FastMCP object; but scope is tools subset, not necessarily conversation server. |

## Risks

1. Adapter lifecycle conflict: `MCPServerAdapter.run(agent)` calls `agent.run()` in a thread then blocks in `self.mcp.run(transport="stdio")`. If the bridge's `mcp_server` is a client shim to an already-running Hermes server, `run()` should probably be a no-op or controlled background startup, otherwise it may try to run a second server.
2. Event-loop/threading risk: adapter handlers await `self.mcp.list_tools()` and `self.mcp.call_tool()` inside uAgents protocol handlers. A shim that owns a long-lived MCP client session must be safe across the uAgents event loop/thread model.
3. Return-type mismatch: adapter assumes `list_tools()` returns an iterable of objects with `.name`, `.description`, `.inputSchema`. MCP Python `ClientSession.list_tools()` returns a result object, typically with `.tools`; shim must unwrap.
4. Tool result mismatch: adapter stringifies list outputs with `"\n".join(str(r)...)`; MCP tool results may be `TextContent`/content blocks or structured content. Shim should normalize to a clean string or sequence acceptable to adapter.
5. ASI:One hard dependency: `MCPServerAdapter` chat flow calls `https://api.asi1.ai/v1/chat/completions` and requires `asi1_api_key`. The pure uAgent MCP protocol handlers do not need ASI, but Chat Protocol discovery/chat does.
6. Public endpoint/security: exposing Hermes capabilities to unknown agents must treat Agentverse discovery as identity/discovery only, not trust. Default allowlist/tool allowlist and redaction are mandatory.
7. Hermes package uncertainty: in the inspected `hermes-agent` 0.13.0 wheel, `hermes mcp serve` dispatch references `mcp_serve.run_mcp_server`, but no `mcp_serve.py` was present. Verify installed CLI before building around it.
8. Version drift: uagents-adapter requires `mcp>=1.8.1`; Hermes dev extra pins `mcp==1.26.0`; latest inspected MCP SDK is 1.27.1. Pin exact versions in spike.

## Recommended spike plan to prove/disprove direct wrapping of Hermes MCP

Goal: determine if Hermes can be exposed as a Fetch.ai uAgent through `uagents-adapter` with no custom protocol implementation, and if not, define the minimal shim.

### Spike A: verify adapter with a trivial official FastMCP object

1. Create a tiny `mcp.server.fastmcp.FastMCP` server with one `echo(text: str) -> str` tool.
2. Instantiate `MCPServerAdapter(mcp_server=mcp, asi1_api_key=dummy-or-real, model="asi1-mini")`.
3. Without running Agentverse, call `await mcp.list_tools()` and `await mcp.call_tool("echo", {"text":"hi"})` directly to confirm object method shape.
4. Run a local uAgent with adapter protocols included; send direct `ListTools` and `CallTool` uAgent messages if possible before testing Chat Protocol.

Success: adapter lists/calls the test tool. Failure here means version/API mismatch.

### Spike B: verify Hermes `hermes mcp serve` actually starts

1. In a clean virtualenv, install `hermes-agent==0.13.0` plus any extra needed for MCP if not installed by default.
2. Run `hermes mcp serve --verbose` and capture stderr/stdout separation.
3. Use MCP Python SDK stdio client to initialize, list tools, and call a benign tool/conversation method.
4. If `mcp_serve` import fails, record as package bug/blocker and switch to `agent.transports.hermes_tools_mcp_server` or local source checkout.

Success: stdio MCP session can list and call Hermes MCP tools. Failure: direct process wrapping is blocked until Hermes package/source issue is resolved.

### Spike C: build minimal stdio client shim object

Implement `HermesMCPClientShim` with:
- `async list_tools(self) -> list[MCPTool]`: returns `result.tools` from `ClientSession.list_tools()`.
- `async call_tool(self, name, args)`: calls `ClientSession.call_tool(name, args)` and normalizes content blocks to strings.
- `def run(self, transport="stdio")`: either no-op if client session starts lazily, or starts/keeps a background MCP client session to `hermes mcp serve`.

Use MCP SDK client APIs (`stdio_client`, `StdioServerParameters`, `ClientSession`) from the official SDK. This converts a transport endpoint/process into the in-process shape expected by `MCPServerAdapter`.

Success: `MCPServerAdapter(mcp_server=HermesMCPClientShim(...))` can list/call Hermes MCP through the adapter. Failure: adapter lifecycle/threading is incompatible; move to a custom uAgent protocol/chat bridge.

### Spike D: test in-process Hermes FastMCP builder if available

1. Try importing `agent.transports.hermes_tools_mcp_server._build_server()` and passing returned FastMCP object to `MCPServerAdapter`.
2. Confirm list/call work without `server.run()`.
3. Determine if this surface is enough for v1; it is a curated Hermes tools server, not necessarily full `hermes mcp serve` conversation server.

Success: fastest path for limited tools bridge. Failure/insufficient scope: use stdio shim around `hermes mcp serve`.

### Spike E: E2E Fetch/uAgent path

1. Create uAgent with `Agent(name=..., seed=..., port=...)` and include `mcp_adapter.protocols` with `publish_manifest=True` if using Agentverse discovery.
2. First test direct uAgent `ListTools`/`CallTool` locally.
3. Then test Chat Protocol with a real ASI:One key and a safe, read-only Hermes tool.
4. Add allowlist, per-tool timeout, max payload size, redacted logging, and disabled dangerous tools before any public endpoint test.

## Recommendation

For v1, do not rely on direct `MCPServerAdapter(mcp_server=<stdio command or URL>)`; it is not supported. Build a small, explicit shim that presents the adapter's expected in-process method shape while using MCP SDK client transports under the hood. This keeps Hermes unchanged and preserves a clean later upstream path: the shim can become a Hermes-native uAgents platform/plugin if the adapter proves stable.
