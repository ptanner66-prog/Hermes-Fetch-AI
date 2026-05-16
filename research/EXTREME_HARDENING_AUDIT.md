# Extreme Hardening Audit
Date accessed: 2026-05-16
Status: final pre-implementation adversarial pass.

This audit supersedes `research/HARDENING_AUDIT.md` where the two conflict. It re-verified the hardened plan against the local public-source evidence under `research/repos/` and `research/pkgs/` and stress-tested API, security, CI, Windows, maintainability, upstream, and autonomous-build failure modes.

## Executive verdict

STATUS: GO for autonomous implementation, with the final build prompt at `research/FINAL_BUILD_PROMPT.md` as the only authoritative implementation prompt.

The plan is credible if and only if the implementation remains a thin policy-aware bridge: Fetch supplies identity, signed envelopes, addressing, discovery, mailbox/proxy/endpoint modes, Almanac/Agentverse rails, in-process dispatcher, and uAgent protocol machinery; Hermes supplies local intelligence, tools, MCP, config, redaction conventions, and execution boundaries; this repo supplies policy, normalization, config, audit, docs, and tests.

No unresolved P0/P1 blocker remains after this pass. The remaining high-risk items have been converted into explicit implementation contracts, tests, stop/ask conditions, or manual-demo-only paths. The autonomous build must pause if any of those contracts proves false.

## Remaining blocking issues

None before starting implementation.

The following are not blockers because the final prompt either avoids them in CI or makes them stop/ask conditions:

1. `hermes mcp serve` is still red/spike-only because `hermes-agent==0.13.0` wheel evidence shows `hermes_cli/mcp_config.py` imports `mcp_serve`, but no `mcp_serve.py` is shipped. The final prompt uses fake MCP for CI and `_build_server()` only for the Hermes-backed local demo.
2. `MCPServerAdapter.protocols` remains unsafe as a v1 boundary because adapter handlers drop sender before `list_tools`/`call_tool`. The final prompt bans it and uses only `uagents_adapter.mcp.protocol` message symbols/spec.
3. Chat protocol remains out of v1. `chat.enable_chat=true` must raise `NotImplementedError`.
4. In-process FastMCP return shape differs from MCP client `ClientSession.call_tool` return shape. The final prompt requires separate normalization for client-side `CallToolResult` and server-side/in-process FastMCP results.
5. Public release contamination cleanup remains required before making the repository public, but not before autonomous implementation. The final prompt gates code/docs contamination in `tests/test_contamination.py`.

## Resolved issues

1. Hermes default path corrected: CI uses fake MCP; Hermes-backed demo uses `_build_server()` with demo-default `skills_list`; `hermes mcp serve` is spike-only.
2. uAgents default network corrected: bridge v1 defaults to `network="testnet"`; mainnet requires explicit operator opt-in.
3. Hosted dependency risk corrected: CI fixtures must use `NoopRegistrationPolicy`, `enable_agent_inspector=False`, `publish_manifest=False`, and in-process dispatcher.
4. Adapter security boundary corrected: build owns `Protocol(spec=mcp_protocol_spec, role="server")`; never publishes `MCPServerAdapter.protocols`; never publishes adapter chat protocol.
5. Tool inventory risk corrected: unknown senders see only explicitly configured `public_tools`; Hermes-backed demo default is `skills_list` only, with every other `EXPOSED_TOOLS` entry denylisted.
6. Dependency consistency corrected: final plan uses exact `mcp==1.27.1` for v1 reproducibility, not an open range.
7. Doctor contradiction corrected: baseline doctor validates `examples/local-direct.yaml` and passes in a clean venv with `dev_random_seed=true`; seed is required only for configs that set `dev_random_seed=false` such as mailbox.
8. Loopback wording corrected: CI must require no hosted/external network; in-process dispatch is the assertion path. A local loopback bind is not itself a failure if it is not required for test assertions.
9. Package-code/examples inversion corrected: fake FastMCP builder lives in `src/hermes_fetch_ai/fake_mcp.py`; `examples/fake_mcp_server.py` imports it. Package code must not import from examples.
10. Windows env filter corrected: Windows subprocess allowlist includes `PATH`, `PATHEXT`, `SystemRoot`, `WINDIR`, `TEMP`, `TMP`, `USERPROFILE`, and Hermes-specific env vars.
11. `ListTools` hardened: per-sender rate limiting and serialized response-size cap apply to `ListTools` as well as `CallTool`.
12. Audit ordering corrected: denied attempts are audited before return; allowed calls audit in `finally` or before send with send-status capture so send failures do not erase the audit trail.
13. Protocol-count test corrected: assert no adapter/chat protocols and exactly one bridge-owned MCP protocol among bridge-included protocols; do not assume uAgents internals have no built-ins.
14. `skills_list` privacy nuance added: it is demo-default only; maximum privacy default can be empty.
15. Push policy corrected: `origin/main` exists; autonomous agent may push normal commits to `origin main` only after tests pass and without force/rebase/amend.

## High-risk API assumptions

### uAgents

Verified local evidence:

- `uagents.Agent` constructor accepts `name`, `port`, `seed`, `endpoint`, `agentverse`, `mailbox`, `proxy`, `registration_policy`, `network`, `loop`, `enable_agent_inspector`, and related args in `research/repos/uAgents/python/src/uagents/agent.py:286-315`.
- Default `network` is mainnet at `agent.py:301`; final v1 config defaults to testnet.
- If no registration policy is supplied, Agent creates a default registration policy at `agent.py:427-436`; final CI supplies `NoopRegistrationPolicy`.
- Agent registers with the module-level dispatcher at `agent.py:398` and `agent.py:457-458`.
- `run_async()` and `run()` exist at `agent.py:1336-1394`.
- `Protocol(spec=..., role="server")` is supported by `research/repos/uAgents/python/src/uagents/protocol.py:26-32` and spec-role validation occurs at `protocol.py:198-216`.
- `Protocol.on_message` defaults to `allow_unverified=False` at `protocol.py:308-313`, registering signed handlers at `protocol.py:368-373`.
- Agent dispatch passes `sender` metadata and selects signed handlers for verified senders at `agent.py:1479-1520`.
- `Context.send` routes through the local dispatcher before network routing at `research/repos/uAgents/python/src/uagents/context.py:467-484`.

Risk posture: signed sender identity is routing/authentication evidence, not authorization. Bridge policy still gates every `ListTools` and `CallTool` decision.

### uagents-adapter

Verified local evidence:

- `uagents_adapter.mcp.protocol` exports `ListTools`, `ListToolsResponse`, `CallTool`, `CallToolResponse`, and `mcp_protocol_spec`, not a generic `ToolResponse`, at `research/repos/uAgents/python/uagents-adapter/src/uagents_adapter/mcp/protocol.py:9-42`.
- Adapter constructs `Protocol(spec=mcp_protocol_spec, role="server")` at `adapter.py:65`.
- Adapter `protocols` returns both MCP and chat protocols at `adapter.py:73-76`.
- Adapter `ListTools` and `CallTool` handlers receive `sender` but call `self.mcp.list_tools()` and `self.mcp.call_tool(msg.tool, msg.args)` without sender/policy at `adapter.py:81-121`.
- Adapter `run()` starts `agent.run()` in a thread and calls `self.mcp.run(transport="stdio")` at `adapter.py:413-424`.

Risk posture: import message models/spec only. Never pass the bridge shim to `MCPServerAdapter`. Never publish `MCPServerAdapter.protocols`.

### MCP SDK and FastMCP

Verified local evidence:

- `mcp.ClientSession.call_tool(name, arguments, ...)` returns `types.CallToolResult` at `research/repos/python-sdk/src/mcp/client/session.py:299-322`.
- `ClientSession.list_tools()` returns `types.ListToolsResult` at `session.py:393-407`.
- FastMCP `list_tools()` and `call_tool()` exist in local FastMCP evidence at `research/repos/fastmcp/fastmcp_slim/fastmcp/server/server.py:615-662` and `server.py:1143-1195`.
- Hermes imports `mcp.server.fastmcp.FastMCP` in `_build_server()`, but the local python-sdk main branch is a V2 rework where stable v1 FastMCP evidence is not representative. Final plan pins `mcp==1.27.1`.

Risk posture: never assume server-side FastMCP results and client-side `CallToolResult` have the same shape. Normalize both.

### Hermes

Verified local evidence:

- `_build_server()` exists at `research/pkgs/src/hermes_agent-0.13.0-py3-none-any/agent/transports/hermes_tools_mcp_server.py:100`.
- `EXPOSED_TOOLS` is defined at `hermes_tools_mcp_server.py:60-97` and includes side-effecting tools such as web, browser, image generation, TTS, and kanban mutation tools.
- Hermes base package does not include MCP; `mcp==1.26.0` is in extras in `hermes_agent-0.13.0.dist-info/METADATA`.
- `hermes mcp serve` dispatch imports `mcp_serve` at `hermes_cli/mcp_config.py:749-755`, but no `mcp_serve.py` is in the inspected wheel.
- Hermes MCP client hardening patterns exist in `tools/mcp_tool.py`, including stderr handling, filtered subprocess env, and credential-like error stripping.
- Hermes redaction/logging patterns exist in `agent/redact.py` and `hermes_logging.py`.

Risk posture: `_build_server()` is private and suitable for demo fallback only. CI must not require Hermes install. Upstream PR should not depend on private functions as a long-term public seam.

## Security failure modes

1. Sender spoofing / over-trust: a signed uAgent sender is authenticated by uAgents runtime but must not be authorized without explicit policy.
2. Sender-blind inventory: unfiltered `ListTools` leaks tool names/schemas and may leak local skill metadata. Must filter and rate-limit per sender.
3. Sender-blind invocation: denied or unknown tools must never invoke the shim.
4. Schema bypass: validate args against normalized `inputSchema` before invocation. Missing schema normalizes to `{type: object, properties: {}}`; extra-arg behavior follows explicit schema policy.
5. SSRF: URL-like strings must reject localhost, private ranges, link-local, IPv4-mapped IPv6, non-obvious local IP forms, and DNS/redirects to private ranges if any HTTP fetching is ever exposed.
6. Path/shell injection: remote args must never be shell-expanded. Stdio subprocesses use `shell=False` and static command/args from config.
7. Subprocess secret leakage: env forwarded to stdio MCP subprocesses is allowlisted; secrets are opt-in only.
8. stderr leakage/corruption: MCP subprocess stderr must be redirected to a temp/log file or null and never contaminate MCP stdout or bridge logs.
9. Audit leakage: logs/audit never include raw args, raw outputs, seeds, tokens, API keys, raw prompts, or full sender addresses.
10. Output DoS: output truncation is deterministic with an explicit marker and byte count.
11. Input DoS: `CallTool.args` byte cap enforced before shim call; `ListToolsResponse` serialization cap enforced.
12. Rate abuse: per-sender rate limiting applies to `ListTools` and `CallTool`.
13. Chat surprise: chat protocol absent in v1; enabling chat raises `NotImplementedError`.
14. Seed/address handling: doctor reports configured/missing/random only; never prints seed or seed fragments.

## CI failure modes

1. Accidental Almanac/Agentverse calls from default registration policy. Mitigation: `NoopRegistrationPolicy` and network-trap fixture.
2. Manifest publication from `Agent.include(..., publish_manifest=True)`. Mitigation: false in CI.
3. Inspector/server flows from `enable_agent_inspector=True`. Mitigation: false in CI.
4. Default mainnet address. Mitigation: testnet in all v1 samples.
5. Plain `uagents-adapter` missing MCP extra. Mitigation: dependency is `uagents-adapter[mcp]==0.6.2`.
6. Hermes not installed in CI. Mitigation: unit suite uses fake MCP; Hermes-backed tests are gated by env.
7. `hermes mcp serve` missing. Mitigation: spike-only, detected by `probe-hermes`.
8. FastMCP in-process result shape passing while stdio fails. Mitigation: tests cover both server-side and client-side normalization paths.
9. Brittle protocol-count assumptions. Mitigation: assert bridge-included protocols and absence of adapter/chat, not all uAgents internals.
10. False contamination failures from LICENSE. Mitigation: LICENSE carve-out for license/legal boilerplate.

## Windows failure modes

1. Paths with spaces (`C:\Users\ptann\OneDrive\Work\Hermes Fetch AI`). All docs/commands quote paths where needed.
2. PowerShell activation differs from POSIX. Docs include `.venv\Scripts\Activate.ps1` and `. .venv/bin/activate` separately.
3. Python launcher differs. Docs mention `py -3.12` and `python`.
4. Executable resolution differs. Docs mention `where hermes` on Windows and `which hermes` on POSIX.
5. `hermes.exe` resolution needs `PATHEXT` and `PATH`.
6. Subprocess creation can fail without `SystemRoot`/`WINDIR`/`TEMP`/`TMP`.
7. Shell quoting is fragile; implementation must avoid `shell=True`.
8. MCP stdio stderr must be redirected to avoid corrupting stdout.
9. Audit default path is `%LOCALAPPDATA%\HermesFetchAI\audit.jsonl`, not inside the repo.
10. Event-loop behavior differs across Python versions; v1 supports Python 3.11 and 3.12 only.

## Upstream PR concerns

1. Preferred upstream shape is a Hermes-native command/plugin such as `hermes uagents serve`, not a gateway `BasePlatformAdapter` unless maintainers request it.
2. Optional dependency strategy is mandatory; do not bloat default Hermes install.
3. Upstream Hermes tool execution must run Hermes' pre/post tool-call hooks. Standalone v1 cannot promise that for private internals.
4. Do not upstream research prompts, contamination audits, vendored evidence caches, standalone CLI wrapper details, or fake demo code except as test fixtures.
5. Attribute Apache-2.0 uAgents/uagents-adapter message-model imports.
6. `_build_server()` is private; any upstream PR should replace it with a stable supported seam.

## Exact corrections applied

1. Created `research/FINAL_ARCHITECTURE_DECISION.md` as the superseding architecture document.
2. Created `research/FINAL_BUILD_PROMPT.md` as the superseding autonomous build prompt.
3. Created `research/GO_NO_GO.md` with `STATUS: GO`.
4. Updated `research/OPEN_QUESTIONS.md` so no P0/P1 blockers remain and added the FastMCP/client result-shape question as a build-time required answer.
5. Updated `research/CONTAMINATION_AUDIT.md` to include `EXTREME_HARDENING_AUDIT.md`, `FINAL_ARCHITECTURE_DECISION.md`, `FINAL_BUILD_PROMPT.md`, and `GO_NO_GO.md` in the scan scope.
6. Final docs consistently ban `MCPServerAdapter.protocols` as the v1 security boundary.
7. Final docs consistently ban chat protocol in v1.
8. Final docs consistently use exact `mcp==1.27.1`.
9. Final docs correct the normal push policy now that `origin/main` exists.
10. Final docs add Windows env allowlist, `ListTools` rate/cap controls, audit-before-return ordering, and package-internal fake server placement.

## Final decision

GO. The autonomous build is allowed to start from `research/FINAL_BUILD_PROMPT.md`. It must stop and ask if any final prompt stop condition triggers, especially if a core safety test would need to be skipped, a new dependency is needed, hosted services become required for CI, `hermes mcp serve` appears fixed upstream, or the local API evidence contradicts an implementation contract.
