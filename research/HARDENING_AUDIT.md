# Hardening Audit
Date accessed: 2026-05-16
Audit role: senior adversarial architect, pre-implementation.
Scope: every research deliverable in `research/`, the existing build prompt, and the two operator prompts at the repo root.
The audit is source-verified against the vendored evidence under `research/repos/` and `research/pkgs/src/` at the commits/versions noted in `research/RESEARCH_INDEX.md`. Where the existing research was correct, the audit confirms it; where it was wrong, ambiguous, or unsafe, the audit names the issue and proposes the fix that is folded into `HARDENED_ARCHITECTURE_DECISION.md` and `HARDENED_BUILD_PROMPT.md`.
## Verdict
Yellow-green. The plan is mostly right and is a connection project, not a reinvention. The thinnest-reliable-bridge framing holds. The plan still contains several issues that would cost real time, real safety, or real CEO-demo credibility if shipped unchanged. None are fatal. All are fixable before any code is written.
The three core fixes the hardened deliverables enforce:
1. The bridge MUST own its direct uAgent protocol and apply policy before any MCP call. `MCPServerAdapter.protocols` is sender-blind after handler dispatch and is unsafe as the default boundary. Existing research already says this — the hardened build prompt makes it non-negotiable and removes any wording that suggests the unmodified adapter is the security surface.
2. The Hermes-side path the existing plan calls "preferred" (`hermes mcp serve`) is not provable from the `hermes-agent==0.13.0` wheel: `hermes_cli/mcp_config.py:754` does `from mcp_serve import run_mcp_server` and **no `mcp_serve.py` is shipped in that wheel**. The hardened plan demotes `hermes mcp serve` to "spike only" and makes the **fake MCP server** the CI-grade default, with `agent.transports.hermes_tools_mcp_server._build_server()` exposing only `skills_list` as the Hermes-backed safe-demo path.
3. The local CI E2E demo must run two uAgents in a single Python process, using the in-process `dispatcher` (`uagents/dispatch.py` module-level singleton) and a no-op `registration_policy` and `enable_agent_inspector=False`, to avoid hitting Almanac, Inspector REST, or any hosted dependency. The existing plan does not say this clearly enough.
The rest of this audit is the punch list.
## Blocking issues (must fix before code)
### B1. `hermes mcp serve` is not callable from the published wheel
- Evidence: `research/pkgs/src/hermes_agent-0.13.0-py3-none-any/hermes_cli/mcp_config.py:749-756` dispatches `mcp serve` to `from mcp_serve import run_mcp_server`. A full `find` over the wheel confirms no `mcp_serve.py`, no `mcp_serve/` package, and no other definition of `run_mcp_server` is present. `hermes_cli/main.py:11997` lists `mcp serve` as a real "agent command" expected to work.
- Risk: any plan that lists `hermes mcp serve` as the "preferred" demo path assumes a top-level module that is not in the artifact. The bridge would `ModuleNotFoundError` on its very first real run.
- Fix (folded into hardened docs):
  - Demote `hermes mcp serve` to "Spike B / optional" status.
  - Promote the fake MCP server to the CI-grade default.
  - Allow `agent.transports.hermes_tools_mcp_server._build_server()` as a Hermes-backed read-only fallback, with `skills_list` as the only default-allowed tool because every other entry in `EXPOSED_TOOLS` is side-effecting (browser automation, web extract/search via Firecrawl, image gen, TTS).
### B2. The MCP install extra is undocumented in the build plan
- Evidence: `hermes_agent-0.13.0.dist-info/METADATA` shows `mcp==1.26.0` only in extras `dev`, `mcp`, `computer-use`, `termux`, `all`. The base install pulls no MCP. Existing `HERMES_MCP_SURFACE.md` says "dev extra" only; that's incomplete.
- Risk: `BUILD_PROMPT.md` says "verify imports and package versions" without spelling out that to even reach `hermes mcp` code paths, the test environment must install `hermes-agent[mcp]==0.13.0`.
- Fix: the hardened build prompt pins explicit install commands and tells `doctor` to test both `hermes-agent` and `hermes-agent[mcp]` paths and to print a clear "install hermes-agent[mcp]" hint when MCP is missing.
### B3. Local CI E2E requires a no-op registration policy
- Evidence: `uagents/agent.py:429-436` creates a `DefaultRegistrationPolicy` if none is passed. `registration.py:148-164` swallows Almanac API errors as warnings but `:574-585` re-raises non-`InsufficientFundsError` ledger exceptions. `agent.py:1106-1107` schedules `publish_manifest` against `agentverse.almanac_api` as a background task on `include(protocol, publish_manifest=True)`.
- Risk: any CI run that constructs an `Agent` with the defaults will (a) try to hit `agentverse.ai`/Almanac REST, (b) optionally try to register on Almanac contract over RPC, and (c) post manifests over HTTP. CI on a clean network may pass because exceptions are warnings — but the test becomes flaky, slow, and emits noisy logs that bury the actual signal. On a corporate network, lookups can hang past pytest timeouts.
- Fix (folded): the hardened build prompt mandates
  - a `NoopRegistrationPolicy(AgentRegistrationPolicy)` used in CI tests;
  - `enable_agent_inspector=False` in CI tests;
  - `publish_manifest=False` in CI tests (production demo turns it on);
  - a dedicated `tests/conftest.py` fixture that sets `AGENTVERSE_URL` to `http://127.0.0.1:0` or similar to short-circuit accidental network calls.
### B4. uAgent `Agent` defaults to mainnet, and the bridge wants testnet
- Evidence: `uagents/agent.py:301` — `network: AgentNetwork = "mainnet"`. Existing `FETCH_UAGENTS_SURFACE.md` does not name the default and the build prompt does not name the v1 default either.
- Risk: a production-looking `agent...` mainnet address may accidentally end up in screenshots, demo videos, or Agentverse; a test wallet on mainnet looks suspicious to maintainers.
- Fix: hardened plan defaults v1 demos to `network="testnet"` (yielding `test-agent...` addresses) and documents this. Production endpoint config may switch to mainnet only with explicit operator opt-in.
### B5. Adapter sender-blindness is documented but not enforced
- Evidence: `research/repos/uAgents/python/uagents-adapter/src/uagents_adapter/mcp/adapter.py:78-121` — `ListTools` and `CallTool` handlers both receive `sender` and never thread it into `self.mcp.list_tools()` / `self.mcp.call_tool(...)`. `protocols` property at `:73-76` returns BOTH `mcp_proto` AND `chat_proto`.
- Existing fix in `ARCHITECTURE_DECISION.md` is correct in spirit but parts of `BUILD_PROMPT.md`, `E2E_DEMO_PLAN.md`, and `MCP_ADAPTER_SPIKE_PLAN.md` still read as if `MCPServerAdapter.protocols` will eventually be the security boundary if the spike passes.
- Risk: a tired implementor will copy the adapter README, include `adapter.protocols`, and ship sender-blind authorization to a CEO demo.
- Fix (folded): the hardened plan bans `adapter.protocols` from `uagent_app.py` entirely. The bridge reuses `mcp_protocol_spec`, `ListTools`, `ListToolsResponse`, `CallTool`, `CallToolResponse` from `uagents_adapter.mcp.protocol` (so wire compatibility is preserved) and binds its OWN `Protocol(spec=mcp_protocol_spec, role="server")` with policy-aware handlers. Chat is implemented (if implemented at all) as a separate bridge-owned protocol, never `adapter.chat_proto` unmodified.
## Major risks
### M1. Plan over-claims that `MCPServerAdapter` is a useful base for shim integration
The shim pattern (`MCPServerAdapter(mcp_server=HermesMCPClientShim(...))`) was floated as a path. It is not necessary for v1 and actively dangerous because it would reintroduce the sender-blind handlers from M1/B5 and the blocking `self.mcp.run(transport="stdio")` call from `adapter.py:413-426` (which would try to "run" the shim like a FastMCP server).
The hardened plan removes shim-into-adapter wiring from v1. The shim is consumed only by the bridge's policy-aware direct protocol. The adapter is downgraded to "reference for message shapes and possible later chat demo only."
### M2. Hermes tools FastMCP exposes side-effecting tools, NOT a safe-demo surface
`agent/transports/hermes_tools_mcp_server.py:60-97` exposes `web_search`, `web_extract`, `browser_navigate`/`_click`/`_type`/`_snapshot`/`_screenshot`/`_scroll`/`_back`/`_press`/`_vision`, `vision_analyze`, `image_generate`, `text_to_speech`, plus `kanban_*` worker handoff tools.
Of those, only `skills_list` and `skill_view` are obviously read-only with no external side effects. Web search via Firecrawl spends paid quota and emits outbound network. Browser tools control a real Chromium/Camofox session. Image generation spends paid quota. TTS does likewise.
Risk: a build agent will read `EXPOSED_TOOLS`, conclude it's a safe demo surface because the module name says "tools", and wire it open by default. The hardened plan locks the bridge's allowlist for unknown senders to `skills_list` (or empty) and explicitly forbids browser/web/image/tts tools from being public-safe.
### M3. Plan does not address Windows-vs-POSIX stdio subprocess differences
Hermes mcp_tool.py:99-148 documents that stdio subprocesses must redirect stderr to a file because MCP uses stdin/stdout for protocol — otherwise the user's TTY corrupts. The bridge shim will face the same issue. On Windows, subprocess creation is more fragile (cmd-vs-PowerShell paths, `python` vs `py`, `.exe` resolution, console allocation flags).
Fix: the hardened shim must explicitly:
- pass `StdioServerParameters(command=..., args=..., env=...)` with a filtered env;
- redirect subprocess stderr to a temp file or null (not the bridge's stderr) so adapter logs don't get mangled;
- avoid `shell=True` and shell-quoting of remote args (which would re-open command injection across the trust boundary).
### M4. Adapter chat path uses synchronous `requests.post` from an async handler
Evidence: `adapter.py:225-340` calls `requests.post(...)` directly inside `ChatMessage` handler. This blocks the event loop and starves other uAgent handlers under any concurrency. It also bypasses the policy layer entirely.
The hardened plan declares the adapter chat path out-of-scope for v1. A bridge-owned chat protocol, if ever implemented, will use `httpx.AsyncClient` and apply policy after model tool selection.
### M5. The "use uAgents-adapter for direct MCP and only customise chat" pattern is rejected
Some places in existing docs still suggest a path where v1 keeps the adapter's `mcp_proto` handlers but adds a policy wrapper. That doesn't work: `MCPServerAdapter._setup_mcp_protocol_handlers` re-binds handlers onto its own `self.mcp_proto` at construction time. You cannot monkey-patch the handlers without forking the class. The clean answer is what B5 says: own the protocol with `Protocol(spec=mcp_protocol_spec, role="server")`. The hardened plan bans the "wrap adapter handler" path.
### M6. `result_normalizer` must guard against MCP `Tool` objects with no `inputSchema`
The adapter does `tool.inputSchema` directly. Some FastMCP tools have `inputSchema={"type": "object", "properties": {}}` (always-empty); others may have `None` after schema generation failures. The shim's `list_tools()` must normalize missing `inputSchema` to `{"type": "object", "properties": {}}` to avoid downstream None-handling bugs in the policy layer or wire serialization.
### M7. `ClientSession.call_tool` returns `CallToolResult`, not a sequence
Evidence: `mcp/client/session.py:368-397` and `mcp/server/fastmcp/server.py:343-346`.
- Server-side `FastMCP.call_tool(name, args)` returns `Sequence[ContentBlock] | dict[str, Any]`.
- Client-side `ClientSession.call_tool(name, args)` returns `types.CallToolResult` with `.content`, `.isError`, `.structuredContent`.
These are not the same shape. The shim is on the client side (it owns a `ClientSession`); the existing wording in `MCP_ADAPTER_SPIKE_PLAN.md` calls `shim.call_tool()` and treats it like FastMCP. The hardened plan splits the shim API:
- `await shim.list_tools() -> list[mcp.types.Tool]` (unwraps `ListToolsResult.tools`).
- `await shim.call_tool(name, args) -> NormalizedToolResult` (unwraps `CallToolResult.content` / `.structuredContent` / `.isError`).
The bridge's `direct_protocol` handlers consume `NormalizedToolResult` and produce the wire `CallToolResponse(result=..., error=...)`. The `result_normalizer` module owns the unwrap.
### M8. `mcp` SDK V2 will remove `mcp.server.fastmcp` (future trap)
The local `python-sdk` clone is on `main` (the V2 rework — see `research/repos/python-sdk/AGENTS.md` "main is currently the V2 rework. Breaking changes are expected"). In V2, `mcp.server.fastmcp` is gone, replaced by `mcp.server.mcpserver`. The bridge pin `mcp==1.27.1` is still safe today. A `>= 1.27` constraint would not be safe.
Fix: the hardened plan pins `mcp` with an upper bound (`mcp>=1.27.1,<2.0`) and notes the migration in `docs/troubleshooting.md`.
### M9. uagents-adapter pulls heavy dependencies including `openai`
`uagents-adapter==0.6.2` declares unconditional dependencies on `openai>=1.0.0`, `requests>=2.32.0`, `httpx>=0.25.0`, `click>=8.0.0`, and `uvicorn>=0.27.0`. The MCP extra adds `mcp>=1.8.1` (looser than the bridge pin).
Fix: the hardened plan documents that installing `uagents-adapter` brings in `openai` and `requests`, regardless of whether chat is enabled, and instructs the audit log redactor to treat any inadvertent ASI/OpenAI request URL as a redactable secret.
### M10. uAgents `Agent.__init__` reuses a global event loop policy
`uagents/agent.py:358` uses `asyncio.get_event_loop_policy().get_event_loop()` which, when called outside a running loop, returns the policy's loop. On Python 3.12+ this triggers a DeprecationWarning. On Python 3.14 it is an error. The bridge should run with `python>=3.11,<3.13` for v1 unless it explicitly creates and passes a loop to `Agent(loop=...)`.
Fix: the hardened plan pins `python>=3.11,<3.13` for v1 and documents the 3.13/3.14 risk as an open item, plus a `doctor` check.
## Minor risks
### m1. Plan does not name a stable `network=` default for the bridge
See B4. Default mainnet is wrong for a research/demo bridge.
### m2. Plan does not specify how the agent's seed is randomized in tests
For CI, generating a random seed per test process avoids accidental fixed-address reuse across CI runs. The hardened plan asks for a `dev_random_seed: true` flag that derives a per-process random seed and prints the address but does not persist it.
### m3. README/docs draft does not yet mention "no funded wallet required"
A Fetch.ai engineer reviewing the README will look for whether the bridge needs a funded wallet for Almanac contract registration. The hardened plan adds an explicit "no funded wallet required for v1: API-only registration via `DefaultRegistrationPolicy.AlmanacApiRegistrationPolicy`; ledger registration is best-effort and skipped on `InsufficientFundsError`" line, with source pointer to `registration.py:548-585`.
### m4. `MCP_ADAPTER_SPIKE_PLAN.md` Spike A install command uses non-extra `uagents-adapter==0.6.2`
`pip install uagents-adapter==0.6.2` does not pull `mcp` (it's an optional extra). The spike command should be `pip install uagents-adapter[mcp]==0.6.2 mcp==1.27.1`. Hardened build prompt fixes this.
### m5. Plan does not specify the audit log path policy
The build prompt says JSONL audit but does not say where the file lives. Default should be `${XDG_STATE_HOME:-~/.local/state}/hermes-fetch-ai/audit.jsonl` on POSIX and `%LOCALAPPDATA%\HermesFetchAI\audit.jsonl` on Windows, NOT inside the repo. Hardened plan fixes this.
### m6. Tests do not include a contamination unit test
The existing build prompt asks the agent to run a contamination scan as a step, but does not encode it as a pytest test. The hardened plan adds `tests/test_contamination.py` that fails CI if any forbidden term appears in `src/`, `docs/`, `examples/`, or `README.md`. The allowed locations for the term list (operator prompts and audit) are explicitly carved out.
### m7. Plan does not describe how the bridge handles oversize MCP outputs
MCP responses can be megabytes. The bridge needs a hard byte/char cap that returns a truncated response with an explicit "truncated" marker instead of streaming raw output. Hardened plan adds an explicit default cap (e.g. 64 KiB content + 16 KiB stderr) and tests for both.
### m8. `direct_protocol.py` was not specified in `REPO_IMPLEMENTATION_PLAN.md`'s file tree
The build prompt mentions it in narrative text but the file tree at `REPO_IMPLEMENTATION_PLAN.md:11-67` omits it. Hardened plan and build prompt add it explicitly.
## Source/evidence gaps
### G1. ASI:One API contract is not source-verified
The adapter calls `https://api.asi1.ai/v1/chat/completions` (`adapter.py:226-229`). No primary source from ASI is captured. Since chat is off-by-default, this is non-blocking for v1; flagged for follow-up if chat ever ships.
### G2. Agentverse mailbox token flow is documented only via uAgents docs, not source-traced
`uagents/mailbox.py` exists in the local clone but no audit of its handshake/timeouts is captured. Non-blocking for v1 because mailbox is optional. Hardened `OPEN_QUESTIONS.md` keeps this as a "non-blocking" item.
### G3. uAgent `Protocol` spec compatibility across versions
`mcp_protocol_spec = ProtocolSpecification(name="MCPProtocol", version="0.1.0", ...)` from `uagents_adapter/mcp/protocol.py:37-42`. Whether spec name+version+role digests are wire-stable across `uagents-core` patch releases is not source-verified. Non-blocking but worth a smoke test in the doctor command.
### G4. Hermes `hermes mcp serve` packaging bug or intentional
We do not know whether `mcp_serve.py` is missing because of a slim-wheel oversight, or because Hermes intends the conversation-MCP server to be loaded from an internal source-only path. Not a v1 blocker because the bridge does not need conversation MCP; the hardened plan documents this as a coordination item with Hermes maintainers.
## Security gaps
### S1. The threat model does not address `CallTool` arg path traversal / SSRF
The policy layer must validate tool arguments by schema. Some Hermes tools (in the broader Hermes universe, not the curated `EXPOSED_TOOLS`) accept URLs, paths, or shell-shaped strings. The bridge must:
- Validate args against the tool's `inputSchema` (jsonschema or equivalent) before dispatch;
- Reject URLs pointing to RFC1918 / link-local / localhost ranges by default when the tool argument is a URL (SSRF guard);
- Never allow argument-expanded shell commands.
Hardened plan adds an `arg_validator.py` step with these defaults and an opt-out for explicit operator-trusted tools.
### S2. The plan does not require uAgent envelope signature verification configurability
uAgents envelopes are signed; the uAgents runtime verifies signatures of `_signed_message_handlers`. The bridge must register its policy-aware handlers as **signed-only** handlers (i.e. use `@protocol.on_message(...)`, not `on_query` for unsigned paths). The hardened plan calls this out and verifies via a test that unsigned envelopes are dropped.
### S3. The plan does not require redaction of the seed in the doctor banner
`doctor` is allowed to print "seed: configured / not configured" but must never print the seed itself nor any prefix/suffix of it. Hardened plan codifies and adds a unit test.
### S4. The plan does not specify rate limiting per sender
Tier 3+ tools and sustained `CallTool` requests need per-sender token-bucket limits. Default deny is good but does not stop an allowed sender from looping. Hardened plan adds a sender-scoped token-bucket rate limit with conservative defaults and a config knob.
### S5. The plan does not handle protocol message-size DoS
uAgents envelopes are JSON; a 50 MB args dict will OOM the bridge before policy runs. The bridge must read a max envelope size at the uAgents server layer if possible, and at minimum reject `CallTool.args` payloads above a configured byte cap before serialization to the shim. Hardened plan adds this.
### S6. The plan does not state how chat protocol publication is enforced
If `enable_chat: false`, the build prompt must guarantee no chat protocol is ever instantiated. The hardened plan: chat code path is in a separate module not imported when `enable_chat` is false; a test asserts `agent.protocols` contains only the bridge direct protocol when chat is off.
## Test gaps
### T1. No test that `MCPServerAdapter.protocols` is not used
The hardened plan adds `tests/test_security_defaults.py::test_adapter_protocols_not_included` which asserts the bridge does not include `mcp_proto` or `chat_proto` from `MCPServerAdapter` in `agent.protocols`.
### T2. No test for in-process two-agent direct E2E
The hardened plan adds `tests/test_uagent_direct_protocol.py::test_local_dispatch_list_and_call` which creates two `Agent` instances with `NoopRegistrationPolicy`, registers a fake MCP server with one safe tool, and asserts a remote agent can `ListTools` and `CallTool` and gets the expected response. Uses the in-process `dispatcher` so no HTTP.
### T3. No test for ListTools sender filtering
The hardened plan adds `tests/test_direct_protocol_policy.py::test_unknown_sender_sees_only_public_safe_tools` and `::test_allowlisted_sender_sees_allowed_tools`.
### T4. No test for normalizer handling `isError` from MCP
Add `tests/test_result_normalizer.py::test_iserror_returns_error_response`.
### T5. No test for seed redaction
Add `tests/test_security_defaults.py::test_doctor_does_not_leak_seed`.
### T6. No test for environment-variable filtering for stdio subprocess
The shim should pass only a small, explicit allowlist of env vars to the subprocess (e.g. `PATH`, `HOME`/`USERPROFILE`, `HERMES_HOME`, `HERMES_QUIET`, `HERMES_REDACT_SECRETS`). Add `tests/test_mcp_shim_fake_server.py::test_stdio_subprocess_env_is_filtered`.
### T7. No test for upper bound on `CallTool.args` size
Add `tests/test_security_defaults.py::test_oversize_args_rejected_before_shim_call`.
### T8. No test for the contamination scan
Add `tests/test_contamination.py` per m6.
### T9. No test for default-deny under empty policy config
Add `tests/test_policy.py::test_empty_config_denies_everything`.
### T10. No test that chat protocol is absent when disabled
Add `tests/test_security_defaults.py::test_chat_protocol_absent_without_config`.
## Docs gaps
### D1. No troubleshooting entry for "ModuleNotFoundError: mcp_serve"
The hardened plan adds this exact entry: it is the predicted top failure mode.
### D2. No section explaining why `MCPServerAdapter.protocols` is not used
This will get asked by Fetch engineers. Add `docs/security.md#why-the-bridge-does-not-use-mcpserveradapter-protocols-directly`.
### D3. No call-out that ASI:One/chat is intentionally off
This will get asked by reviewers of the PR. Add `docs/architecture.md#chat-protocol-is-off-by-default`.
### D4. No mention of the upstream PR ambiguity
`docs/upstream-hermes-pr.md` should lead with "Option B (Hermes-native uAgents serve command/plugin) is the preferred shape because the existing `BasePlatformAdapter` interface is designed for human chat platforms (Telegram/Discord/WhatsApp/Weixin), not RPC transports, and forcing uAgents into it produces ugly mappings." This is more honest than the current "either A or B" framing.
### D5. No Windows-specific demo notes
Bridge stdio shim, hermes invocation, Python path resolution, virtualenv activation, and pytest-asyncio behavior all differ on Windows. Hardened plan adds a Windows section to `docs/demo.md` covering PowerShell `.venv\Scripts\Activate.ps1`, `py -3.12` vs `python`, and `where hermes` resolution.
## Upstream PR risks
### U1. The current UPSTREAM_PR_PLAN.md offers two options without naming a preference
Hardened plan picks Option B (CLI command / plugin) as the recommended shape because:
- `BasePlatformAdapter` (`gateway/platforms/base.py:1259+`) is structured around chat sessions, threads, typing indicators, drafts, voice mode, and human-facing message events. uAgent RPC does not map to those shapes cleanly.
- `PlatformEntry` (`gateway/platform_registry.py:39-80`) expects `adapter_factory(PlatformConfig)`. uAgent identity, seed, network, mailbox, proxy configuration does not fit `PlatformConfig`.
- A `hermes uagents serve --config ...` command (or `hermes mcp serve --bridge uagents`) reads more naturally to Hermes maintainers and keeps the existing MCP server / tool registry boundaries intact.
Option A is documented as a follow-up if Hermes maintainers prefer the platform path.
### U2. The upstream PR plan does not address optional-dependency strategy
`uagents`, `uagents-adapter`, and `mcp` will be `extras_require`/`optional-dependencies` named `uagents`. The PR should not bloat a default Hermes install. Hardened plan adds this.
### U3. The upstream PR plan does not address license/attribution
uAgents and uagents-adapter are Apache 2.0. The bridge inherits/MIT-or-Apache. The eventual upstream PR must attribute reused message-shape imports (`from uagents_adapter.mcp.protocol import ListTools, CallTool, ListToolsResponse, CallToolResponse, mcp_protocol_spec`). Hardened plan adds an "Attribution & License" line to upstream notes.
### U4. The upstream PR plan does not address Hermes' existing approval hooks
Hermes has `_add_accept_hooks_flag` and pre/post tool-call hook plumbing (`hermes_cli/main.py:11129,11176`, `model_tools.py:740+`). A Hermes-native uAgents bridge MUST run the existing `pre_tool_call` hooks for any tool dispatched by an external agent. Standalone v1 cannot run those hooks (they're internal); upstream PR must.
## Recommended corrections to existing files
The hardened deliverables are introduced as new files. In addition, I propose surgical edits to existing files (folded by the next task in this audit's sibling deliverables):
| File | Change |
|---|---|
| `research/MCP_ADAPTER_SPIKE_PLAN.md` | Replace `pip install uagents-adapter==0.6.2 mcp==1.27.1` with `pip install uagents==0.24.2 uagents-core==0.4.4 uagents-adapter[mcp]==0.6.2 mcp==1.27.1`. Mark Spike B as "spike-only; demo path is fake server or `_build_server()`-with-skills_list-only fallback." |
| `research/HERMES_MCP_SURFACE.md` | Clarify that `mcp==1.26.0` is available in extras `dev`, `mcp`, `computer-use`, `termux`, `all` (not just dev). Add Windows stderr note. |
| `research/FETCH_UAGENTS_SURFACE.md` | Add a "default network is mainnet, bridge v1 uses testnet" note. Add an in-process dispatcher note for CI. Document `NoopRegistrationPolicy` pattern. |
| `research/E2E_DEMO_PLAN.md` | Replace "Demo 2 preferred path: `hermes mcp serve`" with "spike-only; Demo 2 default path is `_build_server()` with `skills_list` only, fallback to fake server." |
| `research/REPO_IMPLEMENTATION_PLAN.md` | Add `src/hermes_fetch_ai/direct_protocol.py`, `src/hermes_fetch_ai/arg_validator.py`, `tests/test_contamination.py` to the file tree. |
| `research/SECURITY_MODEL.md` | Add S1–S6 entries (SSRF, signed handlers, doctor redaction, rate limit, envelope size, chat-publication invariant). |
| `research/REPO_SETUP_STATUS.md` | Update — there are now two commits on `main`. |
These are tracked by the next task and applied where they do not duplicate the hardened deliverables.
## Adversarial-question answers
- *What assumption would make this build fail after 12 hours?* "We can just call `hermes mcp serve`." It does not exist in the published wheel.
- *What API mismatch is most likely?* The shim returning a `CallToolResult` to code that expected `Sequence[ContentBlock]`. Owned by `result_normalizer`.
- *What security bug would embarrass the project if public?* `MCPServerAdapter.protocols` exposing the full Hermes tool surface to any signed `agent...` sender on Agentverse.
- *What part of the plan accidentally reinvents Fetch?* Nothing critical now; reusing `mcp_protocol_spec` and `ListTools`/`CallTool` from `uagents_adapter.mcp.protocol` keeps wire compatibility.
- *What part accidentally couples too tightly to Hermes internals?* The `_build_server()` fallback depends on `model_tools.get_tool_definitions` and `handle_function_call`, which in turn need a usable `~/.hermes/config.yaml`. Hardened plan demotes this to "Hermes-backed safe-demo only; fake server is the CI default."
- *What would Teknium-style upstream reviewers reject?* A platform adapter that shoehorns uAgent RPC into the chat-platform `BasePlatformAdapter`. Hardened plan picks the CLI/plugin path as primary.
- *What would Fetch engineers think is naive?* Trusting `sender` for authorization; not setting `network="testnet"`; using mainnet addresses in a research demo.
- *What would a hostile external agent exploit?* Sender-blind `ListTools` (M1/B5), oversize `CallTool.args` (S5), URL-arg SSRF (S1), looping calls without rate limit (S4), chat protocol surprise enablement (S6).
- *What would break on Windows?* stdio subprocess stderr routing (M3), PowerShell vs bash activation, default `asyncio` loop policy on 3.12+, `hermes.exe` PATH resolution.
- *What would break in CI?* Default `DefaultRegistrationPolicy` hitting Almanac (B3); `enable_agent_inspector=True` opening REST endpoints; `publish_manifest=True` posting manifests.
- *What would require live Agentverse credentials?* Mailbox demo, chat protocol, Inspector linking. CI must not need any of these.
- *What can be tested locally without hosted services?* Everything in v1 CI: fake MCP, in-process two-agent direct protocol, policy, normalizer, redaction.
- *What must remain manual/demo-only?* Agentverse Mailbox setup, optional ASI chat, public-endpoint deployment.
- *What must not be public?* Operator prompts at the repo root if/when the repo goes public (they contain guardrail keywords that read oddly outside this private setup).
## What this audit does NOT do
- It does not write code.
- It does not commit anything.
- It does not invent new architecture beyond restating the thinnest reliable bridge and naming the missing safety layer (`HermesMCPClientShim` + policy-aware direct protocol + sender-filtered `ListTools`).
- It does not change the no-OpenClaw / no-legal-tech / no-payments boundaries.
- It does not require Agentverse credentials, ASI keys, or any hosted service to ship v1.
