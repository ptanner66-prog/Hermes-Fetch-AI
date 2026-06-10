# Production Decision: Hermes (Nous Research) x Fetch.ai Bridge

Date: 2026-06-10
Status: authoritative. Extends `research/FINAL_ARCHITECTURE_DECISION.md` with current
upstream evidence and rules on the PR #1 (A2A-first) fork.

## Evidence reviewed (live upstream, 2026-06-10)

### Nous Research `hermes-agent` (v0.16.0, released 2026-06-06, MIT)

- Repo: `github.com/NousResearch/hermes-agent`. Layout: `agent/`, `skills/`, `tools/`
  (40+), `gateway/` (Telegram/Discord/Slack/WhatsApp/Signal/Email), `providers/`,
  `plugins/`, `web/`, `ui-tui/`.
- No uAgents, Fetch.ai, or A2A integration exists upstream. This repo is the connection.
- Hermes exposes TWO distinct MCP server surfaces, and they are not interchangeable:
  1. `mcp_serve.py` (root; `hermes mcp serve`; stdio). Exposes 10 conversation/messaging
     tools: `conversations_list`, `conversation_get`, `messages_read`,
     `attachments_fetch`, `events_poll`, `events_wait`, `messages_send`,
     `channels_list`, `permissions_list_open`, `permissions_respond`. The May packaging
     blocker (`mcp_serve.py` missing from the wheel) no longer reproduces against main:
     the module exists at the repo root. This surface can read private conversations,
     send messages as the operator, and answer permission approvals.
  2. `agent/transports/hermes_tools_mcp_server.py`. Exposes the curated tools registry
     via FastMCP stdio. `EXPOSED_TOOLS` in v0.16.0: `web_search`, `web_extract`,
     `browser_navigate`, `browser_click`, `browser_type`, `browser_press`,
     `browser_snapshot`, `browser_scroll`, `browser_back`, `browser_get_images`,
     `browser_console`, `browser_vision`, `vision_analyze`, `image_generate`,
     `skill_view`, `skills_list`, `text_to_speech`, `kanban_complete`, `kanban_block`,
     `kanban_comment`, `kanban_heartbeat`, `kanban_show`, `kanban_list`,
     `kanban_create`, `kanban_unblock`, `kanban_link`. It still provides
     `_build_server()`, and it is designed for subprocess invocation with a public
     `main()`: `python -m agent.transports.hermes_tools_mcp_server`.

### Fetch.ai rails (`uagents-adapter` 0.6.2, current pin)

- Five official adapters: LangChain, CrewAI, MCP Server, A2A Outbound, A2A Inbound.
- `MCPServerAdapter` requires the Chat Protocol (ASI:One discovery path). This confirms
  the hardened v1 boundary: import only the MCP message models/spec from
  `uagents_adapter.mcp.protocol`; never adopt `MCPServerAdapter.protocols` as the
  security boundary.
- Official A2A Inbound (`SingleA2AAdapter`) exposes a uAgent as an A2A HTTP server on
  Uvicorn + Starlette via the official `A2AStarletteApplication`, serving
  `/.well-known/agent.json`, and is built around the uAgent chat protocol.
- Official A2A Outbound includes AP2 bridging for commerce flows on Fetch rails.
- `uagents` upstream is at 0.25.x (May 2026) with no flagged breaking changes against
  our pinned 0.24.2/core 0.4.4; v0.25.0 added official LangGraph/A2A adapters.

## Decisions

### 1. v1 ships the MCP-over-uAgents bridge on `main`

The production integration is the policy-aware bridge speaking Fetch's published MCP
protocol message models (`ListTools`/`CallTool`) over signed uAgents envelopes, with
default-deny policy, schema/SSRF argument validation, rate limits, bounded outputs,
and redacted audit. This is CI-proven end to end (in-process two-uAgent round trip) on
Python 3.11/3.12.

### 2. The Hermes seam is the tools MCP server, preferred as a hardened stdio subprocess

- Preferred mode: `hermes_mcp.mode: stdio` launching
  `python -m agent.transports.hermes_tools_mcp_server` from the Hermes environment.
  The bridge already hardens this path: `shell=False`, static command/args from
  config, env allowlist, timeouts, stderr separated, output normalization/truncation.
  Process isolation between the uAgent process and Hermes execution is a production
  requirement both orgs get for free here. See `examples/hermes-stdio.yaml`.
- Fallback mode: `in_process_hermes_tools` via `_build_server()` remains supported for
  single-process demos, but it is a private seam and not the production default.
- Permanently out of bridge scope: the `hermes mcp serve` conversations surface.
  Bridging conversation read/send and permission-approval tools across an agent
  network would cross a privacy/impersonation boundary no review at either company
  would accept. This is a design exclusion, not a packaging blocker; the probe's
  `hermes mcp serve` check is retained only as environment evidence.
- Policy for the Hermes-backed config: `skills_list` is the only public tool;
  `skill_view` (private skill content) and every side-effecting tool in
  `EXPOSED_TOOLS` are explicitly denylisted. Denylist wins by construction.

### 3. PR #1 ("A2A-first proof", branch `codex/full-hookup-proof`) is closed

Rationale, in review terms:

- It hand-rolls an A2A JSON-RPC server on stdlib `http.server.ThreadingHTTPServer`
  with hand-rolled bearer auth. Python documents `http.server` as not recommended for
  production; Fetch's own `SingleA2AAdapter` runs the official `a2a-sdk` Starlette
  application on Uvicorn. Reimplementing a rail the partner company officially ships
  fails review at both companies.
- Its A2A dialect is non-standard: tool routing via custom
  `operation=list_tools|call_tool` data parts that no generic A2A client knows. It is
  neither Fetch's adapter nor faithful A2A semantics.
- It embeds three commerce-flow modules. Commerce flows are explicitly excluded from
  v1 scope, and on Fetch rails belong to the official AP2 bridging in the A2A Outbound
  adapter, not to a bespoke protocol in a bridge.
- Salvageable ideas (re-port deliberately later if wanted, without the server):
  mailbox startup test coverage, probe reporting improvements (independently fixed on
  the integration branch), arg-validator simplifications.

### 4. A2A exposure is a v2 front-end via the official adapter only

When A2A reach is wanted, put Fetch's `SingleA2AAdapter` (or its successor) in front
of the same bridge agent. That adapter is chat-protocol based, so adopting it means
consciously accepting the chat boundary that v1 excludes; that acceptance is a v2
decision with its own threat-model review. No hand-rolled A2A or commerce protocol
will be added to this repo.

### 5. Follow-ups

- Evaluate the `uagents` 0.24.2 -> 0.25.x and `uagents-core` 0.4.4 -> 0.4.6 pin bump
  in a dedicated change once 0.25.x has soaked; CI must stay green under the bump.
- Upstream contribution to `NousResearch/hermes-agent` proceeds per
  `research/UPSTREAM_PR_PLAN.md`: open a discussion first; the CLI/plugin shape is
  recommended; the gateway platform-adapter shape only if maintainers ask.

## Why each company signs this

- Fetch.ai: the bridge runs on Fetch's canonical rails (uAgents identity/envelopes,
  published MCP protocol spec, testnet defaults, Almanac/Agentverse optional), uses
  official adapters where they exist, and adds nothing that competes with or forks
  Fetch protocol surfaces.
- Nous Research: Hermes is consumed only through its designed tools MCP surface, in a
  separate OS process, behind default-deny policy with the conversation/permission
  surface structurally unreachable; the repo is MIT-on-MIT and the upstream plan
  follows Hermes plugin conventions.
