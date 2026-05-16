# Open Questions
Date accessed: 2026-05-16
Status: final after extreme hardening. There are no unresolved P0/P1 blockers before autonomous implementation.

## Blocking before code

None.

The build may start from `research/FINAL_BUILD_PROMPT.md`. Every previously blocking architecture/security question now has an explicit decision:

| Question | Final decision | Owner |
|---|---|---|
| Which Hermes-side MCP path is the v1 default? | Fake MCP for CI; `_build_server()` with `skills_list` only for Hermes-backed local demo; `hermes mcp serve` is spike-only until Hermes ships `mcp_serve.py`. | decided |
| Is `MCPServerAdapter.protocols` ever used in v1? | No. Import only message symbols/spec from `uagents_adapter.mcp.protocol`; bridge owns policy-aware handlers. | decided |
| Is chat protocol shipped in v1? | No. `chat.enable_chat=true` raises `NotImplementedError` / config failure. | decided |
| What network is the default? | `testnet`. Mainnet requires explicit operator opt-in. | decided |
| How does CI avoid hosted dependencies? | `NoopRegistrationPolicy`, `enable_agent_inspector=False`, `publish_manifest=False`, fake MCP, in-process dispatcher. | decided |
| What Python versions are supported? | Python 3.11 and 3.12. | decided |
| What is the normal push policy? | `origin/main` exists. After all acceptance checks pass, normal `git push origin main` is allowed. No force-push/rebase/amend. | decided |

## Must answer during implementation

These do not block starting the build, but the coding agent must resolve them before the relevant module is considered complete. If any answer contradicts `research/FINAL_BUILD_PROMPT.md`, stop and ask.

| Question | Why it matters | Where it surfaces |
|---|---|---|
| Does `_build_server()` need a usable `~/.hermes/config.yaml` to return `skills_list`? | Hermes-backed demo may need an operator with a real Hermes config. | `hermes_probe.py`, `mcp_shim.py`, `examples/hermes-local.yaml` |
| Are bridge handlers signed-only in the actual uAgents objects? | Unsigned envelopes must never reach policy. | `tests/test_uagent_direct_protocol.py` asserts no unsigned handler for bridge protocol digests. |
| Does `uagents.Bureau` use the same dispatcher singleton as standalone Agents in this pinned version? | Determines the simplest in-process demo runner. | Tests may use direct dispatcher or Bureau after verification. |
| What does `ClientSession.list_tools()` return when server has zero tools? | Ensures empty inventory path is deterministic. | `tests/test_mcp_shim_fake_server.py` |
| How does the shim handle MCP server crash mid-call? | Reconnect must not retry side-effecting operations unsafely. | `mcp_shim.py`, subprocess tests |
| How does `arg_validator` handle tools with no `inputSchema`? | Some tools may lack schemas. | Missing schema normalizes to `{ "type": "object", "properties": {} }`; extra-arg behavior follows explicit schema policy. |
| How exactly do fake/in-process FastMCP results differ from client-side `CallToolResult`? | Fake mode must not hide stdio/client result-shape bugs. | `result_normalizer.from_fastmcp_result` and `from_call_tool_result` tests. |
| What is the final truncation marker? | Downstream agent should know output was truncated. | `result_normalizer.py`; required marker includes original byte count. |
| What does `doctor` report on Windows when `hermes.exe` is not on PATH? | Common failure mode; must be actionable, not traceback. | `hermes_probe.py`, docs/demo.md, docs/troubleshooting.md |
| Can `ListToolsResponse` serialization exceed cap with many tools? | Inventory is a DoS/leak surface. | `direct_protocol.py`, `tests/test_direct_protocol_policy.py` |

## Non-blocking follow-up after v1

| Question | Why it matters | Likely path |
|---|---|---|
| Mailbox token UI flow in current Agentverse | Polished manual demo needs reliable screenshots/docs. | Manual run outside CI. |
| Public HTTPS endpoint hardening | Required before long-running public deployment. | Separate v2 design. |
| Does standalone `fastmcp==3.x` interop with the bridge? | Nice-to-have if official SDK changes. | Future compatibility spike. |
| Scheduled outbound mode | Different consent/rate model. | v2 only. |
| More IPv6/DNS SSRF edge cases | Environment-specific. | Add cases as reported. |
| Multiple shims behind one uAgent address | Federation/multi-backend use. | v2 only. |
| SQLite audit mirror | Easier queries. | v2 optional. |
| Hermes publishes a stable uAgents/MCP seam | Could simplify upstream integration. | Track Hermes releases and upstream PR discussion. |

## Explicitly out of scope for v1

| Topic | Reason |
|---|---|
| Payments, billing, marketplace pricing | Not the value-add of a connection project. |
| Wallet UX beyond seed/address identity | Fetch/uAgents identity is enough for v1. |
| Per-skill commercial manifests | Out of scope. |
| Domain-specific/private use cases | Public boundary requires general AI-infra framing only. |
| OpenClaw integration | Out of scope by contract. |
| Bridge-owned chat protocol | Adds model-service trust boundary; not justified for v1. |
| Multi-tenant operator hosting | Single operator per process in v1. |
| Hermes gateway platform adapter | CLI/plugin is preferred; platform adapter only if maintainers request it. |

## Current top blockers

None. Status is GO, subject to the stop/ask conditions in `research/FINAL_BUILD_PROMPT.md`.
