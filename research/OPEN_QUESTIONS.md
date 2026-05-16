# Open Questions

Date accessed: 2026-05-16

| Question | Why it matters | Priority | Blocks coding? | Next step |
|---|---|---:|---:|---|
| Does `hermes mcp serve` work from a clean `hermes-agent==0.13.0` install? | Inspected wheel dispatches to `mcp_serve.run_mcp_server`, but `mcp_serve.py` was not found. | P0 | Blocks Hermes-backed stdio demo, not fake-MCP bridge coding. | Run clean venv command in `MCP_ADAPTER_SPIKE_PLAN.md` Spike B. |
| Is the conversation-oriented Hermes MCP surface different from `agent.transports.hermes_tools_mcp_server`? | Determines demo scope: full Hermes conversations vs curated tools. | P0 | Blocks final demo story, not fake-MCP E2E. | Inspect source distribution or live installed package; call `list_tools()`. |
| Does a bridge-owned uAgent direct protocol interoperate cleanly with `uagents-adapter` message models? | V1 should reuse existing rails but cannot rely on sender-blind adapter handlers for security. | P0 | Blocks direct protocol implementation details only. | Build a two-agent local test for `ListTools` and `CallTool` using copied/imported message models. |
| Does the uAgents direct local client need Almanac registration or can it send by known address/endpoint in CI? | Determines reliability of local E2E. | P1 | Could block CI approach. | Build local two-agent test; if hosted registration is involved, use resolver/direct endpoint test fixture. |
| Which Hermes tool is safest for first real demo? | Avoids exposing sensitive or side-effecting operations. | P1 | Blocks CEO demo, not fake E2E. | Prefer fake echo first, then read-only `skills_list` or Hermes status if available. |
| What exact Agentverse token/Inspector steps are needed for mailbox in current UI? | Needed for polished demo docs. | P1 | Does not block core build. | Follow official mailbox docs with a test agent and record screenshots/log messages outside repo. |
| Do standalone `fastmcp==3.3.1` objects interoperate with `uagents-adapter`? | Nice-to-have; adapter docs use official SDK import, not standalone package. | P2 | No. | Test only if official SDK path is insufficient. |
| Should upstream Hermes integration be gateway platform or MCP/plugin command? | Affects later PR shape. | P2 | No for standalone. | Ask Hermes maintainers after standalone proof. |

## Resolved by adversarial review

- Do not use unmodified `MCPServerAdapter.protocols` as the default v1 security boundary. Its handlers know `sender` but do not pass sender into the MCP object, so a sender-blind shim cannot enforce sender-aware policy.
- Do not publish chat by default. `MCPServerAdapter.protocols` includes chat; v1 direct MCP must work without ASI, and chat requires explicit config, key, redaction, timeouts, and post-selection policy.
- Do not expose full tool inventory to unknown senders. `ListTools` must be sender-filtered.

## Current top blockers

1. Hermes `hermes mcp serve` package verification.
2. Direct uAgent local E2E mechanics without hosted dependency.
3. Choosing the first safe Hermes-backed tool surface.
4. Agentverse/Mailbox UI/token steps for a polished external demo.
