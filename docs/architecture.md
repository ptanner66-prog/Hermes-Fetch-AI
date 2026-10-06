# Architecture

Hermes Fetch AI has three layers:

1. Fetch.ai's uAgents provide identity (signed sender addresses) and message delivery.
2. The bridge passes every `ListTools`/`CallTool` message through rate limits, policy, replay protection, and argument checks, caps the response size, and writes a redacted audit record.
3. Hermes' tools MCP server, or the built-in fake tools, run the tool locally behind the MCP shim.

Message flow:

```text
sender
  -> signed uAgent MCP message
  -> rate limits, default-deny policy, replay protection
  -> JSON-schema + URL/shell argument checks
  -> MCP shim
  -> Hermes tools server (stdio subprocess) or fake tools
  -> result normalizer (size cap)
  -> response + audit record
```

Trust boundaries:

- A signed sender address identifies the caller but authorizes nothing by itself.
- The tool list is filtered and rate-limited, because it discloses what the local install can do.
- `CallTool` is replay-protected at the bridge, before any tool runs.
- Hermes' tools server runs as a separate process with `shell=False`, a filtered environment, and stderr kept apart from the protocol stream.
- Almanac registration is off in the example configs, and a private bridge makes no outbound calls of its own.
- Seeds come from the environment only.

## Design decisions

1. **v1 is MCP over uAgents.** The bridge speaks Fetch's published MCP message models (`ListTools`/`CallTool` from `uagents_adapter.mcp.protocol`) over signed uAgents envelopes. It imports only the message models and spec, not `MCPServerAdapter`, whose protocols would sit in front of this package's policy checks and pull in the chat protocol.
2. **The Hermes integration point is the tools MCP server, run as a separate process.** `python -m agent.transports.hermes_tools_mcp_server` serves Hermes' curated tool registry over stdio. Running it as a child process (`shell=False`, a static command, an environment allowlist, timeouts, stderr discarded) keeps Hermes execution out of the network-facing uAgent process. The in-process mode is a fallback for hermes-agent v0.16.x because it calls a private Hermes function.
3. **Hermes' conversations surface is permanently out of scope.** `hermes mcp serve` exposes conversation reads, message sends, and permission approvals. Bridging those onto an agent network would let remote agents read private conversations or act as the operator.
4. **Hermes-backed configs are default deny.** `skills_list` is the only public tool. `skill_view` (full skill content) and every other tool the server offers are denylisted by exact name, and the denylist wins over any allowlist.
5. **A2A could be a v2 front end, not part of v1.** Fetch's A2A inbound adapter is built around the chat protocol, so adopting it means accepting the chat boundary v1 excludes, with its own threat-model review. If it is added, it goes in front of this same bridge agent.
6. **A private bridge stays silent.** uAgents looks up the Almanac contract on the Fetch ledger whenever an agent is created, and reports every agent as active at startup and inactive at shutdown through Agentverse's Almanac API, even when registration is disabled. With `publish_manifest: false`, the bridge uses `PrivateAgent`, which skips both, so it makes no outbound calls of its own. Tests check both the private and the published case.
7. **The Hermes plugin is a sidecar, not an in-process integration.** Hermes pins `mcp==2.0.0`, while this package pins `mcp==1.28.1` (the version it is tested with) and supports Python 3.11/3.12, so they cannot share an environment. The `fetchai-bridge` directory plugin is stdlib-only (`python_runtime: external`): it runs the separately installed `hermes-fetch-ai` and hands it Hermes' interpreter, so `serve` starts the tools server the way Hermes does. An in-process plugin would have forced the bridge's dependencies into Hermes' environment. See [`hermes-plugin.md`](hermes-plugin.md).
8. **Policy state belongs to a protocol instance.** Rate-limit windows and the replay cache live in a `PolicyState` that `build_protocol` creates, not in module globals, so two bridges in one process, or two tests, never share state.

## Failure behavior

- If Hermes' tools server cannot start (bad command, crash on import, initialize timeout), `serve` exits with status 1 and `hermes backend: FAIL` instead of serving an empty tool list, so a supervisor such as systemd can restart it or alert. If the HTTP server cannot start (the port is taken), `serve` exits with status 1 and `serve: FAIL`.
- If the backend stops responding after startup, `ListTools` and `CallTool` return `backend unavailable`, the audit log records `decision: error`, and the bridge logs the failure.
- A backend transport error during a call returns `tool call failed`; the details go to the bridge's log.
- Unexpected exceptions while handling `CallTool` return a generic `internal bridge error`; the traceback goes to the bridge's redacted log with the audit record's `trace_id`.
