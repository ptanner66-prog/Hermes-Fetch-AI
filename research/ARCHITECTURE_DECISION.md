# Architecture Decision

> Hardened note (2026-05-16): For final v1 decisions, see `research/HARDENED_ARCHITECTURE_DECISION.md`, `research/HARDENED_BUILD_PROMPT.md`, and `research/HARDENING_AUDIT.md`. Where this file disagrees with the hardened deliverables, the hardened deliverables are authoritative.

Date accessed: 2026-05-16

## Executive recommendation

Build Hermes Fetch AI v1 as the thinnest reliable bridge: a standalone Python package that exposes a uAgent with Fetch/uAgents discovery and messaging, while forwarding allowed requests into Hermes through MCP. Start with `uagents-adapter` direct MCP protocols, but do not depend on it directly wrapping `hermes mcp serve`. The adapter expects an in-process object with `list_tools()`, `call_tool()`, and `run()`, so v1 should provide a small Hermes MCP client shim that presents that object shape while using the official MCP Python SDK client transports under the hood.

This is a connection project. Fetch supplies identity, addressing, discovery, Agentverse/Almanac rails, mailbox/proxy/endpoint modes, and chat/uAgent protocols. Hermes supplies the local agent/execution environment, tool registry, MCP client/server concepts, config/secrets, redaction, and operator boundaries.

## Decision

First implementation path:

1. `hermes-fetch-ai` starts a uAgent using pinned Fetch packages: `uagents==0.24.2`, `uagents-core==0.4.4`, `uagents-adapter==0.6.2` for reference models/compatibility, and `mcp==1.27.1` for MCP client transports.
2. Do **not** publish `MCPServerAdapter.protocols` wholesale by default. The upstream adapter's direct handlers receive `sender` but discard it before calling `self.mcp.list_tools()` / `self.mcp.call_tool(...)`, which makes sender-aware authorization impossible in a sender-blind shim.
3. Build a policy-aware direct MCP uAgent protocol in the bridge, reusing the adapter's message shapes where practical. Its handlers must call `policy.authorize(sender, tool, args, protocol)` before any shim/MCP access and must audit allow/deny decisions.
4. Implement `ListTools` as sender-filtered inventory: unknown senders see only explicitly public-safe tools or an empty list; allowlisted senders see only their explicitly allowed tools. Never expose the full Hermes tool inventory by default.
5. The policy-aware handler calls a `HermesMCPClientShim` object, not a raw CLI command or URL. The shim uses MCP SDK client APIs to connect over:
   - preferred spike: Hermes `hermes mcp serve` stdio, if the installed package actually starts; or
   - fallback spike: Hermes `agent.transports.hermes_tools_mcp_server._build_server()` in-process FastMCP object for limited tools.
6. Publish the adapter chat protocol only when `enable_chat: true`, `ASI1_API_KEY` is present, redacted logging is configured, and the same sender/tool policy runs after model tool selection. Chat is off by default.
7. Agentverse Mailbox and ASI:One chat are demo/production options, not the required CI path. The required CI path is local direct uAgent-to-uAgent `ListTools` and `CallTool` through the policy-aware protocol.

## Why the connection is already mostly built

The connection is mostly built, but not as one turnkey command:

- Fetch/uAgents already provides identity, addressing, envelopes, protocol handlers, Agentverse/Almanac discovery, direct endpoint mode, mailbox mode, proxy mode, and protocol manifest publication. See official docs in `RESEARCH_INDEX.md` and uAgents source at `python/src/uagents/agent.py`, `registration.py`, `resolver.py`, `mailbox.py`.
- `uagents-adapter==0.6.2` already provides an MCP-facing uAgent protocol and Agent Chat Protocol bridge. Its `MCPServerAdapter` calls `await self.mcp.list_tools()` and `await self.mcp.call_tool(...)` and exposes `ListTools`/`CallTool` messages. Source: `uAgents/python/uagents-adapter/src/uagents_adapter/mcp/adapter.py` at commit `6d7008971eaff74e0a0ca564c19d666f5047ef1a`.
- The official MCP Python SDK already provides the FastMCP object shape and stdio/SSE/streamable HTTP server/client transports. Source: `modelcontextprotocol/python-sdk` at commit `161834d4aee2633c42d3976c8f8751b6c4d947d5`.
- Hermes already has MCP client infrastructure and at least one FastMCP server builder for a curated Hermes tools surface. Local public wheel references: `tools/mcp_tool.py:1-220`, `agent/transports/hermes_tools_mcp_server.py:100-186`.

The missing thin layer is Hermes-specific packaging and safety: a client shim/lifecycle manager, bridge config, tool/sender policies, redacted logging, tests, docs, and demos. Do not build a new agent network, marketplace, wallet UX, or replacement execution framework.

## Message flow

Minimal direct uAgent flow:

1. Operator runs `hermes-fetch-ai serve --config config.yaml`.
2. Bridge loads `UAGENT_SEED`, optional `ASI1_API_KEY`, optional Agentverse token, and Hermes MCP command/config from environment/config.
3. Bridge constructs a uAgent with stable seed, direct endpoint or mailbox/proxy settings.
4. Bridge constructs `HermesMCPClientShim`, configured to start/connect to Hermes MCP.
5. Bridge constructs a policy-aware direct MCP uAgent protocol. It may reuse `uagents-adapter` message shapes, but it must not include unmodified `MCPServerAdapter.protocols` as the default security boundary.
6. Remote uAgent discovers address/protocol via known address, Almanac, Agentverse, or local direct config.
7. Remote sends `ListTools` or `CallTool` envelope to the bridge uAgent address.
8. uAgents verifies envelope/addressing enough to route, but bridge treats sender as untrusted input.
9. For `ListTools`, bridge fetches candidate tools from the shim only if safe, then returns sender-filtered tool inventory. Unknown senders see only public-safe tools or an empty list.
10. For `CallTool`, bridge policy checks sender, protocol, tool allowlist, payload size, schema, rate limit, and side-effect requirements before any MCP invocation.
11. Shim calls Hermes MCP `list_tools` or `call_tool` through an MCP SDK session only after policy allows it.
12. Hermes executes the allowed MCP/tool action within its normal local execution boundaries.
13. Shim normalizes MCP content blocks to protocol-compatible string/JSON result.
14. uAgent sends response envelope back to the sender.
15. Audit log records sender address, tool name, decision, timing, truncated/redacted input/output hashes or snippets, and errors.

Agentverse chat flow is the same except the adapter's chat protocol asks ASI:One to select/compose a tool response. That adds an ASI API key and model-service trust boundary. It is optional for v1 acceptance.

## Trust boundaries

- uAgent seed: private identity key. If leaked, the agent can be impersonated.
- Agent address: identity/discovery, not authorization.
- Almanac/Agentverse: discovery and routing, not trust.
- Mailbox/Agentverse token: account/linking credential; never commit or log.
- ASI:One API key: model-service credential; optional for chat demo; never required for direct protocol CI.
- Remote sender payload: untrusted input even when signed/routed.
- Bridge policy layer: authorization and safety enforcement point.
- Hermes MCP server: local privileged execution boundary.
- Hermes tools: potentially side-effecting; expose only explicit allowlist.

## Alternatives rejected

### A. Pass `hermes mcp serve` directly to `MCPServerAdapter`

Rejected for v1 because `MCPServerAdapter` has no command/args/URL transport config. It stores an object and invokes `self.mcp.list_tools()`, `self.mcp.call_tool()`, and `self.mcp.run(transport="stdio")`. A CLI subprocess is not that object shape.

### B. Import Hermes internals and build the final upstream adapter in the standalone repo

Rejected for v1. It couples a private standalone proof to Hermes internal lifecycle and makes the later upstream PR look pasted-in. Use the standalone repo to prove behavior through stable CLI/MCP seams first. Importing `_build_server()` is acceptable as a spike/fallback, not as the only design.

### C. Implement a custom Fetch protocol from scratch instead of `uagents-adapter`

Rejected for v1 unless the adapter fails the spike. Existing adapter already maps MCP tools to uAgent protocols and Agent Chat Protocol. A custom protocol would increase surface area and risk without proving current rails insufficient.

### D. Make Agentverse/ASI chat the only demo path

Rejected for CI and first build. Hosted login/API-key dependencies are fine for a CEO demo, but the build must have a local deterministic test path: bridge uAgent plus local client uAgent sending `ListTools`/`CallTool`.

## Production-grade path

MVP path proves direct local `ListTools`/`CallTool` through `uagents-adapter` to Hermes MCP with a read-only echo/status tool.

Production-grade path adds:

- mailbox/proxy/public endpoint examples;
- Agentverse profile/readme metadata;
- optional ASI chat demo with explicit API-key setup;
- sender allowlists and tool policies;
- rate limiting, timeouts, payload/output caps;
- redacted structured audit logs;
- integration tests against a fake MCP server and, where available, Hermes MCP;
- documented version pins and upgrade tests;
- narrow upstream Hermes PR plan.

## Confidence

Yellow-green. Fetch/uAgents and `uagents-adapter` provide enough rails to avoid new architecture. The only yellow blockers are Hermes `hermes mcp serve` package verification and adapter lifecycle/threading with a client shim.
