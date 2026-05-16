# Hermes MCP Surface

Date accessed: 2026-05-16

Sources are public package artifacts from `hermes-agent==0.13.0` inspected under `research/pkgs/src/hermes_agent-0.13.0-py3-none-any/`.

## Package and dependency facts

- PyPI live metadata: `hermes-agent==0.13.0`, Python `>=3.11`.
- The inspected wheel metadata lists `mcp==1.26.0` under the `dev` extra, not as a base runtime dependency. Treat MCP server/client usage as an optional dependency path that must be explicitly installed in the bridge environment.

## CLI surface

### `hermes mcp serve`

Local source: `hermes_cli/main.py:11105-11129`.

The parser describes `hermes mcp` as managing MCP server connections and running Hermes as an MCP server. It says:

- `hermes mcp serve` runs Hermes as an MCP server and exposes conversations to other agents.
- `--verbose` enables verbose logging on stderr.
- `_add_accept_hooks_flag(...)` is attached, which means hook/approval behavior may affect server startup.

Dispatcher source: `hermes_cli/mcp_config.py:749-756`.

The `serve` action executes:

```python
from mcp_serve import run_mcp_server
run_mcp_server(verbose=getattr(args, "verbose", False))
```

Important blocker: the inspected wheel did not contain a top-level `mcp_serve.py`. That could be a packaging omission, namespace quirk, or mismatch in extracted artifacts. Do not assume `hermes mcp serve` works until a spike starts it in a clean environment.

### `hermes mcp add`

Local source: `hermes_cli/main.py:11131-11155`.

Flags include:

- `--url` for HTTP/SSE endpoint URL.
- `--command` and `--args` for stdio server commands.
- `--auth oauth|header`.
- `--preset`.
- `--env KEY=VALUE` for stdio server env vars.

This proves Hermes can consume external MCP servers over URL or stdio, but it does not prove `uagents-adapter` can consume Hermes over those transports without a shim.

## Hermes MCP client implementation

Local source: `tools/mcp_tool.py:1-220`.

The module-level comments document:

- Stdio transport using command + args.
- HTTP/streamable HTTP transport using URL.
- SSE transport for MCP servers using SSE.
- automatic reconnection with exponential backoff.
- environment variable filtering for stdio subprocesses.
- credential stripping in error messages returned to the model.
- configurable timeouts for tool calls and connection.
- thread-safe architecture with a dedicated background event loop.
- sampling support for server-initiated LLM requests.

Implementation imports and feature detection include:

- `from mcp import ClientSession, StdioServerParameters`
- `from mcp.client.stdio import stdio_client`
- optional `streamablehttp_client` / `streamable_http_client`
- optional `sse_client`

Design implication for Hermes Fetch AI: reuse these concepts, not the entire module. The standalone bridge should implement a small MCP client shim with the same discipline: dedicated lifecycle, timeouts, redacted stderr/logging, env filtering, reconnect behavior, and clear failure states.

## Hermes tools-as-MCP server

Local source: `agent/transports/hermes_tools_mcp_server.py:1-225`.

This module exposes a curated subset of Hermes tools to a Codex subprocess via MCP. Key facts:

- `_build_server()` imports `mcp.server.fastmcp.FastMCP` and returns a FastMCP server object (`:100-186`).
- It builds a server named `hermes-tools` (`:117-126`).
- It obtains authoritative Hermes tool schemas via `model_tools.get_tool_definitions(quiet_mode=True)` (`:111-134`).
- It registers selected tools by building Python callables that call `model_tools.handle_function_call(tool_name, kwargs)` (`:149-160`).
- `main()` sets `HERMES_QUIET=1` and `HERMES_REDACT_SECRETS=true`, builds the server, and runs it over default stdio (`:189-215`).
- Logs go to stderr because MCP uses stdout/stdin for protocol (`:194-198`).

This is not necessarily the full conversation-oriented `hermes mcp serve` surface. It is a good spike target because it returns the exact in-process FastMCP object shape that `MCPServerAdapter` expects.

## Tool registry and execution boundaries

Local source: `tools/registry.py:151-290,320-390`.

Relevant behavior:

- `ToolRegistry` holds `ToolEntry` objects, toolset checks, and aliases under a lock (`:151-180`).
- `register(...)` is called by tool modules at import time (`:234-248`).
- It rejects shadowing between non-MCP toolsets, while allowing MCP-to-MCP overwrites for refresh/overlap (`:250-272`).
- `get_definitions(...)` returns OpenAI-format function schemas only for available tools (`:320-367`).
- `dispatch(...)` executes handlers and catches exceptions into JSON errors (`:373-390`).

Bridge implication: the standalone bridge should not bypass Hermes' tool registry assumptions. It should expose only explicit allowlisted MCP tools, preserve schema validation, and never let remote tool names shadow or invent local tool access.

## Config, secrets, and logging surfaces

### Config home and env files

Local source: `hermes_cli/config.py:1-120,360-408`.

Hermes stores configuration under `~/.hermes/`:

- `~/.hermes/config.yaml` for model/toolsets/terminal/etc.
- `~/.hermes/.env` for API keys and secrets.

The module contains lock/caching logic for config reads and secure file/dir handling. `_secure_file` uses owner-only permissions except in managed/container cases (`:360-375`). `ensure_hermes_home()` creates `cron`, `sessions`, `logs`, `memories`, and related directories (`:387-408`).

Bridge implication: do not write bridge secrets into repo files. Use `.env`/environment variables and document secret names. If the bridge reads Hermes config, do so as a consumer; do not mutate Hermes config except in a future upstream PR.

### Redaction

Local source: `agent/redact.py:1-120,311-405`.

Hermes has regex-based secret redaction for logs and tool output. It masks API keys, tokens, private keys, connection strings, URL query secrets, form bodies, and userinfo. `RedactingFormatter` applies `redact_sensitive_text(...)` to log records (`:395-405`).

Bridge implication: use redacted structured logging by default. Treat raw remote prompts, tool args, tool outputs, seeds, API keys, and Agentverse tokens as sensitive. Log hashes/truncated summaries unless debug mode is explicitly enabled.

## Gateway/platform/plugin literacy for later upstream PR

Local source: `gateway/platform_registry.py:1-80`.

Hermes has a `PlatformEntry` registry with:

- `name`, `label`, `adapter_factory`, `check_fn`, `validate_config`, `is_connected`, `required_env`, and `install_hint`.
- The registry allows plugin adapters to self-register and lets gateway creation avoid hardcoded chains.

Local source: `gateway/platforms/base.py:1-170`.

Platform adapters follow a base interface for receiving/sending platform messages and integrating with the gateway runtime.

Upstream implication: the eventual Hermes PR should look like a normal Hermes platform/plugin integration, likely adding a uAgents platform/plugin that maps uAgent inbound messages into existing gateway/session machinery rather than copying the standalone runner wholesale.

## What the standalone repo should borrow conceptually

Borrow:

- MCP lifecycle discipline: stdio/HTTP/SSE transport handling, stderr redirection, timeouts, reconnects.
- Tool registry respect: schema-driven tool lists, explicit toolsets/allowlists, no shadowing.
- Config/secrets discipline: env/config separation, `.env` ignored, owner-only files where possible.
- Redaction and auditability.
- Platform adapter pattern for later upstream readability.

Keep outside Hermes until proven:

- Fetch/uAgents dependency pins and demo runner.
- Agentverse mailbox/proxy setup flow.
- ASI:One chat demo code.
- Standalone CLI/config schema and examples.
- Experimental shim variants and compatibility probes.

## Hermes-side blockers

1. Verify `hermes mcp serve` works from a clean `hermes-agent==0.13.0` install. The inspected wheel dispatches to `mcp_serve`, which was not present.
2. Determine whether conversation-level MCP is required for v1 or whether `hermes_tools_mcp_server._build_server()` read-only/safe tool surface is enough for the first demo.
3. Confirm compatible `mcp` version across Hermes package and bridge pins (`1.26.0` dev extra vs `1.27.1` current PyPI).
