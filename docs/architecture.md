# Architecture

Hermes Fetch AI has three layers:

1. Fetch/uAgents identity and messaging provide signed sender addresses and delivery.
2. The bridge filters list/call messages through policy, replay protection, argument validation, redaction, audit, and output normalization.
3. Hermes or fake MCP tools execute locally behind the shim.

Message flow:

```text
sender
  -> signed uAgent MCP message
  -> bridge policy/rate-limit/replay gate
  -> JSON-schema + URL/shell argument validation
  -> MCP shim
  -> local Hermes/fake tool
  -> result normalizer/redactor
  -> bounded response + audit event
```

Trust boundaries:

- Sender address is not enough to authorize a tool call.
- Tool inventory is filtered and rate-limited because list responses can disclose capability information.
- `CallTool` is replay-protected at the bridge boundary before tool invocation.
- MCP subprocesses run with `shell=False`, a filtered environment, and stderr separated from protocol output.
- Hosted registration is disabled in local configs.
- Production seed material comes from the environment only.

The production-preferred Hermes seam is the Hermes tools MCP server launched as a hardened stdio subprocess (`examples/hermes-stdio.yaml`); the in-process builder is a demo fallback. Existing Fetch, Hermes, and MCP rails are sufficient for v1. The bridge only connects them with local policy and audit.

`MCPServerAdapter.protocols` is not used as the v1 security boundary because it exposes protocol behavior before this package's policy checks. Chat is out of v1 scope to keep the surface narrow.

A2A exposure, if added later, goes through Fetch's official A2A inbound adapter in front of this same bridge agent, never a hand-rolled protocol server.

## Design decisions

1. **v1 is MCP over uAgents.** The bridge speaks Fetch's published MCP message models (`ListTools`/`CallTool` from `uagents_adapter.mcp.protocol`) over signed uAgents envelopes. It imports only the message models and spec, not `MCPServerAdapter`, because the adapter's protocols would sit in front of this package's policy checks and pull in the chat protocol.
2. **The Hermes seam is the tools MCP server, run as a separate process.** `python -m agent.transports.hermes_tools_mcp_server` exposes the curated Hermes tools registry over stdio. Running it as a child process (`shell=False`, static command and args, environment allowlist, timeouts, stderr discarded) keeps Hermes execution isolated from the network-facing uAgent process. The in-process `_build_server()` mode is a demo fallback because it depends on a private Hermes function.
3. **The Hermes conversations surface is permanently out of scope.** `hermes mcp serve` exposes conversation reads, message sends, and permission approvals. Bridging those across an agent network would let remote agents read private conversations or act as the operator, so the bridge never connects to it.
4. **Hermes-backed configs are default deny.** `skills_list` is the only public tool. `skill_view` (private skill content) and every side-effecting tool are denylisted by exact name, and the denylist wins over any allowlist.
5. **A2A is a possible v2 front end, not part of v1.** Fetch's official A2A inbound adapter is built around the chat protocol, so adopting it means accepting the chat boundary that v1 excludes, with its own threat-model review.

## Failure behavior

- If the Hermes backend cannot start (bad command, crash on import, initialize timeout), `serve` exits with status 1 and a `hermes backend: FAIL` message instead of serving an empty tool list, so a supervisor such as systemd can restart it or alert.
- If the backend stops responding after startup, `ListTools` and `CallTool` return `backend unavailable`, the audit log records `decision: error`, and the bridge logs the failure.
- Unexpected exceptions while handling `CallTool` return a generic `internal bridge error` to the caller; the traceback goes to the bridge's redacted log with the audit `trace_id`.
