# Hardened Architecture Decision
Date accessed: 2026-05-16
Status: final v1 decision after adversarial review.
Supersedes the v1 sections of `research/ARCHITECTURE_DECISION.md` for any disagreement; non-disputed material in that file remains valid.
## TL;DR
Hermes Fetch AI v1 is a thin Python bridge that exposes Hermes Agent as a discoverable Fetch.ai uAgent by:
1. Owning a small `uagents.Protocol(spec=mcp_protocol_spec, role="server")` that reuses the wire-compatible `ListTools`/`CallTool` message models from `uagents_adapter.mcp.protocol` but binds **its own** policy-aware handlers.
2. Routing allowed calls through a `HermesMCPClientShim` that uses the official `mcp==1.27.1` Python SDK client transports (stdio first, optional SSE/streamable HTTP later).
3. Treating uAgent sender identity as routing, not authorization. Default-deny tools. Sender-filtered `ListTools`. Audited allow/deny decisions.
4. Defaulting v1 to a **fake MCP server** for CI and to `agent.transports.hermes_tools_mcp_server._build_server()` (with the `skills_list` tool only) for the Hermes-backed local demo. `hermes mcp serve` is spike-only because the published `hermes-agent==0.13.0` wheel is missing `mcp_serve.py`.
5. Not publishing `MCPServerAdapter.protocols` at all, ever, in v1. Not publishing chat by default. Chat, mailbox, proxy, ASI:One, Agentverse public endpoint, public HTTPS deployment are all out of v1 CI; documented as optional demo paths.
Confidence: **green** for CI-grade direct uAgent demo with fake MCP server; **yellow-green** for Hermes-backed local demo via `_build_server()` + `skills_list`; **yellow** for Agentverse Mailbox / public endpoint; **red** for `hermes mcp serve` until the Hermes packaging issue is resolved upstream.
## What is already built by existing rails
| Layer | Provided by | Evidence |
|---|---|---|
| Cryptographic agent identity (`agent...`/`test-agent...`) | `uagents.Agent` | `python/src/uagents/agent.py:222+`, `config.py` |
| Signed envelopes & routing | uAgents runtime | `agent.py:1135-1148`, `communication.py` |
| In-process two-agent dispatch (no HTTP) | `uagents.dispatch.dispatcher` singleton | `dispatch.py:47-159`; `Agent.__init__` registers at `agent.py:458` |
| Direct endpoint / mailbox / proxy modes | `Agent(endpoint=|mailbox=|proxy=)` | `agent.py:286-380`, `mailbox.py` |
| Almanac registration (API and contract) | `DefaultRegistrationPolicy` | `registration.py:526-585`; API errors swallowed, ledger failures on `InsufficientFundsError` swallowed |
| Protocol manifest publication | `Agent.include(protocol, publish_manifest=True)` | `agent.py:1060-1133` |
| MCP wire message shapes (`ListTools`/`CallTool`/responses, protocol spec) | `uagents_adapter.mcp.protocol` | `protocol.py:9-42` (`mcp_protocol_spec = ProtocolSpecification(name="MCPProtocol", version="0.1.0", roles={"client": set(), "server": {ListTools, CallTool}})`) |
| MCP client transports (stdio/SSE/streamable HTTP) | `mcp` Python SDK | `mcp-1.27.1-py3-none-any/mcp/client/{stdio,sse,streamable_http}.py`, `mcp/client/session.py:368+` |
| MCP server (in-process FastMCP) | `mcp.server.fastmcp.FastMCP` | `mcp-1.27.1-py3-none-any/mcp/server/fastmcp/server.py:146,279,315,343` |
| Hermes tool registry + dispatch | `model_tools.handle_function_call`, `tools/registry.py` | `model_tools.py:697+`, `tools/registry.py:151-390` |
| Hermes tools FastMCP server (curated subset) | `agent.transports.hermes_tools_mcp_server._build_server()` | `hermes_tools_mcp_server.py:60-186` |
| Hermes secret redaction | `agent.redact.RedactingFormatter` | `agent/redact.py:1-120,311-405` |
## What thin layer this repo adds
A standalone Python package `hermes-fetch-ai` providing:
1. **`HermesMCPClientShim`** — owns a long-lived MCP client session over stdio (default), optional SSE/HTTP. Exposes:
   - `async list_tools() -> list[mcp.types.Tool]` (unwraps `ListToolsResult.tools`)
   - `async call_tool(name: str, args: dict | None) -> NormalizedToolResult` (unwraps `CallToolResult.content` / `.structuredContent` / `.isError`)
   - `start()`, `aclose()`, async context manager.
   - Dedicated background loop in a daemon thread (Hermes-style, see `tools/mcp_tool.py:60-65`), so the bridge does not hand session ownership across uAgents/asyncio boundaries unsafely.
   - Subprocess stderr redirected to a file (or null), never the bridge stderr.
   - Env-var filtering: only an explicit allowlist (`PATH`, `HOME`/`USERPROFILE`, `HERMES_HOME`, `HERMES_QUIET`, `HERMES_REDACT_SECRETS`) is forwarded.
2. **`result_normalizer`** — `CallToolResult` → `NormalizedToolResult` (string + JSON, with `isError`, `truncated`, `output_bytes`, optional `structured`). Caps content at 64 KiB by default. Drops binary content blocks to a redacted summary.
3. **`policy`** — pure function module:
   - `visible_tools(sender, tools) -> list[Tool]` — filters tool inventory per sender.
   - `authorize(sender, tool, args, protocol) -> AuthorizationDecision` — returns allow/deny + reason. Default deny. Checks denylist first, sender allowlist, public-tool list, payload size cap, schema validity.
   - `arg_validator` helper: validates `args` against `tool.inputSchema` (jsonschema), rejects RFC1918/localhost URLs for string fields that look like URLs.
4. **`direct_protocol`** — defines/imports `mcp_protocol_spec`, `ListTools`, `ListToolsResponse`, `CallTool`, `CallToolResponse` from `uagents_adapter.mcp.protocol`. Builds a fresh `uagents.Protocol(spec=mcp_protocol_spec, role="server")` with handlers that:
   - call `policy.visible_tools(sender, ...)` BEFORE serializing `ListTools` response;
   - call `policy.authorize(sender, ...)` BEFORE invoking the shim on `CallTool`;
   - audit every allow/deny;
   - return `CallToolResponse(error=...)` on deny, never invoking the shim.
5. **`uagent_app`** — constructs `Agent` with `network="testnet"`, `enable_agent_inspector=False` in CI, optional `mailbox=True` or `proxy=True` in demo configs, optional `NoopRegistrationPolicy` for CI. Includes only the bridge's direct protocol with `publish_manifest=True` in production demos, `False` in CI tests. Never includes `MCPServerAdapter.protocols`.
6. **`audit`** — JSONL writer with timestamp, sender (truncated), tool, decision, reason, duration_ms, args_bytes, output_bytes, error_class, trace_id. No raw args, prompts, tool outputs, seeds, tokens, or API keys.
7. **`logging`** — wraps stdlib logging with a redactor inspired by Hermes' `RedactingFormatter`.
8. **`config`** — YAML + `.env`. Validates `UAGENT_SEED` is present unless `dev_random_seed: true`. Schema is fully versioned and documented.
9. **`cli`** — Typer/argparse with `doctor`, `probe-hermes`, `serve`, `demo local|mailbox`. `doctor` returns non-zero if any required dep is missing, the seed is unset, or the configured `hermes_mcp.mode` is unreachable.
10. **`hermes_probe`** — tries, in order: `hermes --version`, `python -c "from agent.transports.hermes_tools_mcp_server import _build_server; _build_server()"`, `python -m hermes_cli.main mcp serve --help`. Reports each result distinctly.
11. **`examples/`** — `fake_mcp_server.py` (FastMCP echo + add), `local_client.py` (sender uAgent), `local-direct.yaml`, `agentverse-mailbox.yaml`, `hermes-local.yaml`.
12. **`tests/`** — config, policy, normalizer, shim against fake stdio server, in-process two-agent direct E2E, security defaults (chat-off, seed redaction, default-deny, oversize rejection, signed-only handlers), contamination scan.
13. **`docs/`** — architecture, security, demo (with Windows section), troubleshooting, upstream-hermes-pr.
## What is intentionally NOT built in v1
- A new agent network, marketplace, payments, billing, wallet UX beyond the seed/address identity.
- A custom uAgents protocol that re-invents `mcp_protocol_spec`.
- Use of `MCPServerAdapter.protocols`. The adapter is imported only for its message-model exports (`ListTools`, `CallTool`, etc.) and `mcp_protocol_spec`.
- The adapter's chat protocol. ASI:One/chat is documented as a future demo only.
- A Hermes-side gateway platform adapter. The upstream PR plan recommends a Hermes-native `hermes uagents serve` command/plugin, not a `BasePlatformAdapter` subclass.
- Public HTTPS deployment / production hardening (rate-limited public endpoint testing, SSRF blocklists for production, log retention, secret manager integration). All documented as future work.
- Side-effecting Hermes tools (web search, browser automation, image generation, TTS). Allowlist forbids these for unknown senders by default.
- OpenClaw, legal-tech-specific examples, domain-specific use cases.
## V1 message flow (exact)
### Local CI direct flow (no hosted dependencies)
1. Test fixture creates `bridge` and `client` `Agent` instances with `NoopRegistrationPolicy`, `enable_agent_inspector=False`, `publish_manifest=False`, `network="testnet"`, `endpoint=["http://127.0.0.1:8000/submit"]` (unused for in-process dispatch but required by `Agent`).
2. Both agents register with the module-level `uagents.dispatch.dispatcher` at construction (`agent.py:458`).
3. Bridge constructs `FakeMCPServer()` (in-process FastMCP with one `echo` tool) and a `HermesMCPClientShim` wrapping it in-process (no subprocess in CI).
4. Bridge constructs `direct_protocol.build_protocol(shim, policy, audit_log)` and `agent.include(protocol, publish_manifest=False)`.
5. Test starts both agents via `Bureau` (shared loop) or `asyncio.gather` of their `run_async()` methods.
6. Client sends `ListTools()` to `bridge.address` via `await ctx.send(...)`.
7. `Context.send_raw` checks `dispatcher.contains(parsed_address)` (`context.py:477`) and goes through `dispatch_local_message` (`communication.py:103-124`) — no HTTP.
8. Bridge handler receives `(ctx, sender, msg)`. Calls `policy.visible_tools(sender, await shim.list_tools())`. Returns `ListToolsResponse(tools=[...filtered...], error=None)`. Audit log records `allow` decision with sender truncated.
9. Client receives the response and sends `CallTool(tool="echo", args={"text": "hi"})`.
10. Bridge handler validates `args` against the echo tool's `inputSchema`. Calls `policy.authorize(sender, "echo", args, "direct_mcp")`. On allow, calls `await shim.call_tool("echo", args)`. On deny, returns `CallToolResponse(result=None, error="...")` WITHOUT invoking the shim.
11. Shim returns `NormalizedToolResult(text="hi", is_error=False, truncated=False)`. Handler returns `CallToolResponse(result="hi", error=None)`.
12. Client receives the response. Test asserts.
### Hermes-backed local flow
1. Same as above, but step 3 is `HermesMCPClientShim(mode="in_process_hermes_tools")`. The shim imports `agent.transports.hermes_tools_mcp_server._build_server()` lazily.
2. Bridge config sets `policy.public_tools = ["skills_list"]`. `policy.denied_tools` explicitly lists everything else in `EXPOSED_TOOLS` (`hermes_tools_mcp_server.py:60-97`).
3. Client `CallTool(tool="skills_list", args={})` returns the operator's installed skills metadata.
### Production demo flow (Agentverse Mailbox; out of v1 CI)
1. Operator runs `hermes-fetch-ai serve --config examples/agentverse-mailbox.yaml`.
2. Config sets `agent.network: testnet`, `agent.mailbox: true`, `agent.publish_manifest: true`, `hermes_mcp.mode: "stdio"` (or `in_process_hermes_tools`).
3. Bridge starts. Logs print agent address and Inspector mailbox URL.
4. Operator links the mailbox in Agentverse UI.
5. A remote uAgent sends `ListTools` / `CallTool` via Agentverse mailbox. Mailbox client (`uagents/mailbox.py`) delivers the envelope to the bridge agent.
6. Bridge handler runs the same policy-aware path. Returns response. Audit recorded.
7. CEO demo: no funded wallet required (API-only Almanac registration; `registration.py:548-585` skips ledger on `InsufficientFundsError`).
## Exact trust boundaries
```
┌──────────────────────────────────────────────────────────────────────┐
│ Remote uAgent (signed envelope; identity verified by uAgents runtime)│
└────────────────────────────┬─────────────────────────────────────────┘
                             │  uAgents transport (HTTP or mailbox)
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│ uAgents runtime: signature & schema-digest verification.             │
│ Identity = agent address. NOT authorization.                         │
└────────────────────────────┬─────────────────────────────────────────┘
                             │  (sender: str, msg: ListTools|CallTool)
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Bridge policy-aware direct protocol handlers (this repo).            │
│ • signed-only handlers (no on_query)                                 │
│ • size cap on envelope args                                          │
│ • sender-filtered ListTools                                          │
│ • policy.authorize(sender, tool, args, protocol) before shim call    │
│ • arg_validator(jsonschema + URL/SSRF guard)                         │
│ • per-sender rate limit                                              │
│ • audit allow/deny                                                   │
└────────────────────────────┬─────────────────────────────────────────┘
                             │  (only if policy allows)
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│ HermesMCPClientShim (this repo).                                     │
│ • stdio/SSE/HTTP via official mcp SDK ClientSession                  │
│ • subprocess env filtered; stderr to file                            │
│ • per-call timeout                                                   │
│ • normalized result via result_normalizer                            │
└────────────────────────────┬─────────────────────────────────────────┘
                             │  MCP protocol over stdio (default)
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Hermes MCP server (fake in CI, _build_server() locally, or           │
│ `hermes mcp serve` once Hermes ships mcp_serve.py).                  │
│ Local privileged execution; Hermes' own tool registry/policies apply.│
└──────────────────────────────────────────────────────────────────────┘
```
Credential placements (none leave the bridge process intentionally):
- `UAGENT_SEED` — read at startup; derives address; never logged. Required unless `dev_random_seed: true`.
- Agentverse mailbox token — used only in mailbox mode by `uagents/mailbox.py`. Never logged.
- `ASI1_API_KEY` — only loaded if chat is explicitly enabled in a future bridge-owned chat module (not v1).
- Hermes secrets (`~/.hermes/.env`) — Hermes' own concern; bridge does not read or copy them.
## Exact local CI demo path
```bash
# All commands work on Windows PowerShell and on POSIX bash.
python -m venv .venv
.\.venv\Scripts\Activate.ps1     # Windows PowerShell
# . .venv/bin/activate            # bash/zsh
python -m pip install -U pip
python -m pip install -e ".[dev]"
# pyproject pins:
#   uagents==0.24.2
#   uagents-core==0.4.4
#   uagents-adapter[mcp]==0.6.2
#   mcp==1.27.1
#   pydantic>=2.8,<3
#   python-dotenv>=1
#   typer or argparse (no extra dep)
#   pytest, pytest-asyncio, anyio (dev)
#   ruff, mypy (dev, optional)
python -m hermes_fetch_ai.cli doctor
python -m pytest -q
python -m hermes_fetch_ai.cli demo local
```
`demo local` runs the same two-agent in-process flow as the CI test, but logs to the console so an operator can see the round trip.
## Exact production demo path
```bash
$env:UAGENT_SEED = "..."                             # required, do not commit
python -m hermes_fetch_ai.cli probe-hermes
python -m hermes_fetch_ai.cli serve --config examples/agentverse-mailbox.yaml
# Operator opens the Inspector URL printed in logs and links the mailbox.
# Remote uAgent or Agentverse UI sends ListTools / CallTool to the bridge.
```
If `hermes-agent` is installed locally and `_build_server()` works in the operator's environment, set:
```yaml
hermes_mcp:
  mode: in_process_hermes_tools
policy:
  public_tools: ["skills_list"]
  denied_tools:
    - web_search
    - web_extract
    - browser_navigate
    - browser_click
    - browser_type
    - browser_press
    - browser_snapshot
    - browser_scroll
    - browser_back
    - browser_get_images
    - browser_console
    - browser_vision
    - vision_analyze
    - image_generate
    - text_to_speech
    - skill_view              # read-only but reads private skill content; allowlist-only
    - kanban_complete
    - kanban_block
    - kanban_comment
    - kanban_heartbeat
    - kanban_show
    - kanban_list
    - kanban_create
    - kanban_unblock
    - kanban_link
```
`stdio` mode is documented as the future path once `hermes mcp serve` is fixed upstream:
```yaml
hermes_mcp:
  mode: stdio
  command: hermes
  args: [mcp, serve, --verbose]
  env_passthrough: [HERMES_HOME, HERMES_QUIET, HERMES_REDACT_SECRETS]
  timeout_seconds: 30
```
## Why this is the thinnest reliable bridge
We did the source survey to confirm:
- Fetch supplies identity, addressing, discovery, signed transport, manifests, mailbox/proxy, in-process dispatch, and a published `mcp_protocol_spec` and message models.
- The MCP SDK supplies all wire transports we need on the client side.
- Hermes already has its own MCP client and a curated FastMCP server suitable as a Hermes-backed safe-demo backend.
The only things missing are: a policy-aware bridge between sender identity and Hermes tool execution, a shim that adapts client transports to a small object the bridge can call, a normalizer for results, and the operational glue (config, logging, audit, CLI, tests, docs, demos).
That is exactly what this repo builds, and nothing more.
## Confidence level
- **Direct uAgent CI demo with fake MCP server:** green. All dependencies are PyPI-stable, all source paths are verified, in-process dispatcher avoids hosted services entirely.
- **Hermes-backed local demo via `_build_server()` + `skills_list`:** yellow-green. Verified the function exists and returns a FastMCP server; requires a usable `~/.hermes/config.yaml` so `model_tools.get_tool_definitions()` returns a non-empty list; `skills_list` should be present in any normal Hermes install.
- **Agentverse Mailbox / production demo:** yellow. Requires manual UI linking and a stable seed in environment, plus testnet defaults; documented and not in CI.
- **`hermes mcp serve` over stdio:** red until Hermes ships `mcp_serve.py`. Bridge supports the config but `doctor` will report the blocker; switching to `in_process_hermes_tools` or `fake` mode is the documented workaround.
- **Upstream PR shape:** yellow. Two viable shapes; the hardened plan recommends a CLI command/plugin, but Hermes maintainers may prefer the platform-adapter path. The standalone repo's logic ports either way.
## What changes vs. `ARCHITECTURE_DECISION.md`
The original document is broadly correct. The differences this hardened decision enforces:
1. The shim is **not** passed to `MCPServerAdapter`. The bridge consumes the shim directly.
2. `MCPServerAdapter.protocols` is banned in v1.
3. `hermes mcp serve` is demoted from "preferred" to "spike-only" because the wheel is missing `mcp_serve.py`.
4. The CI default is the fake MCP server in-process; `_build_server()` with `skills_list` is the Hermes-backed safe-demo path; `hermes mcp serve` is optional, gated by `doctor`.
5. Default `network="testnet"` for v1 demos.
6. Default `enable_agent_inspector=False` and `publish_manifest=False` in CI; opt-in for demo.
7. `NoopRegistrationPolicy` is a first-class requirement for CI to avoid Almanac/HTTP.
8. Result handling lives in `result_normalizer`, not in the shim, and unwraps `CallToolResult` not `Sequence[ContentBlock]`.
9. Adapter chat is explicitly out of v1; if chat is ever added, it is a **bridge-owned** chat protocol using `httpx.AsyncClient`, not `requests.post`.
10. The upstream PR plan picks Option B (CLI command / plugin) over Option A (platform adapter).
