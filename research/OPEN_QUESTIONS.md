# Open Questions
Date accessed: 2026-05-16
Status: triaged after the hardening audit. Questions are split into four buckets so the build session can act on each.
## Blocking before code
These must be resolved before the autonomous build can start. None of them require new research — they require explicit decisions or commit-once configuration.
| Question | Resolution / decision | Owner |
|---|---|---|
| Which Hermes-side MCP path is the v1 default? | **Fake MCP server for CI; `_build_server()` with `skills_list` for the Hermes-backed local demo.** `hermes mcp serve` is spike-only because the published wheel is missing `mcp_serve.py`. | (decided, hardened plan) |
| Is `MCPServerAdapter.protocols` ever used in v1? | **No.** The bridge owns its own `Protocol(spec=mcp_protocol_spec, role="server")` with policy-aware handlers. Adapter symbols are imported only for message-model wire compatibility. | (decided) |
| Is the chat protocol shipped in v1? | **No.** Config rejects `chat.enable_chat: true` with NotImplementedError. | (decided) |
| What network is the default? | **testnet.** Mainnet only on explicit operator opt-in. | (decided) |
| How does CI avoid hosted dependencies? | `NoopRegistrationPolicy` + `enable_agent_inspector=False` + `publish_manifest=False`, in-process `dispatcher` for two-agent send. | (decided) |
| What Python versions are supported? | **3.11 and 3.12.** 3.13+ is deferred due to `asyncio.get_event_loop_policy()` deprecation surfacing in uAgents 0.24.2. | (decided) |
## Answer during spike (during the build session)
These do not block starting the build but must be answered by the time the relevant module lands.
| Question | Why it matters | Where it surfaces in the build |
|---|---|---|
| Does `_build_server()` need a usable `~/.hermes/config.yaml` to return tool definitions? | If yes, the Hermes-backed local demo needs an operator with a real Hermes install. Test with both an empty and a populated config. | `mcp_shim.py` in_process mode; `hermes_probe.py` reports tool count. |
| Are the bridge's signed-only handlers actually rejecting unsigned envelopes? | Security invariant: unsigned envelopes must never reach policy. | `tests/test_uagent_direct_protocol.py` asserts no unsigned handler is registered for our schema digests; manually craft an unsigned envelope to confirm rejection. |
| Does `uagents.Bureau` use the SAME `dispatcher` singleton as standalone Agents? | Determines whether `Bureau` is needed for in-process CI tests. | `tests/test_uagent_direct_protocol.py`; verified by reading `agent.py:458` (it does — `self._dispatcher = dispatcher` from the module-level singleton). |
| What does `ClientSession.list_tools` return when the server has zero tools? | Confirms the empty-list path is exercised; relevant for unknown-sender ListTools default. | `tests/test_mcp_shim_fake_server.py::test_list_tools_empty`. |
| How does the shim handle MCP server crash mid-call? | Reconnect logic must not retry idempotency-unsafe operations. | `tests/test_mcp_shim_fake_server.py::test_subprocess_crash_returns_error`. |
| How does `arg_validator` handle tools with no `inputSchema`? | Some Hermes tools may have an empty schema; the validator must accept any args in that case. | `tests/test_arg_validator.py::test_missing_input_schema_accepts_anything`. |
| What's the right truncation marker for oversize results? | The downstream uAgent should know the result was truncated; pick a deterministic, unambiguous marker. | `result_normalizer.py`; `tests/test_result_normalizer.py`. |
| What does `doctor` report on Windows when `hermes.exe` isn't on PATH? | Common failure mode; user should see an actionable message, not a traceback. | `hermes_probe.py`; manual test on Windows. |
## Non-blocking follow-up (after v1 ships)
| Question | Why it matters | Likely path |
|---|---|---|
| Mailbox token UI flow in current Agentverse | Polished CEO demo needs reliable docs/screenshots. | Manual run; capture screenshots outside repo; cite official docs in `docs/demo.md`. |
| Public HTTPS endpoint hardening | Required before a long-running public deployment. | Separate doc; not v1. |
| Does standalone `fastmcp==3.3.1` interop with the bridge? | Nice-to-have; adapter docs use official SDK import path. | Test only if the official SDK becomes insufficient. |
| Should v1 ship a `cron`/scheduled outbound mode? | Proactive messaging is a different consent model. | Out of scope for v1; document as v2 work. |
| Does our `arg_validator` SSRF guard fire on IPv6 link-local in all environments? | Real-world IPv6 envs are uneven. | Add more IPv6 cases when an operator reports a miss. |
| Does the bridge support multiple shims behind one address? | Useful for federation; out of v1 scope. | Defer to v2. |
| Should `audit.jsonl` also emit a sqlite mirror? | Easier ad-hoc queries. | Defer; JSONL is fine for v1. |
| Will Hermes ever publish the conversation-MCP serve module? | Affects `hermes mcp serve` path. | Track Hermes releases; the bridge's stdio mode is ready when it ships. |
## Deferred to v2 (explicitly out of scope)
| Topic | Reason |
|---|---|
| Payments, billing, marketplace pricing | Not the value-add of a connection project. |
| Wallet UX beyond seed/address identity | Same. |
| Per-skill commercial manifests | Same. |
| Domain-specific use cases | Public boundary requires general AI-infra framing only. |
| OpenClaw integration | Out of scope by contract. |
| Bridge-owned chat protocol | Adds ASI/OpenAI/model-service trust boundary; not justified for v1. |
| Multi-tenant operator hosting | Single operator per process in v1. |
| Hermes-side platform adapter (`BasePlatformAdapter` subclass) | `BasePlatformAdapter` is for chat platforms; uAgent RPC does not fit cleanly. Use a CLI command/plugin instead — see `docs/upstream-hermes-pr.md`. |
## Resolved by adversarial review (kept here for traceability)
- `MCPServerAdapter.protocols` is sender-blind after handler dispatch and is unsafe as the default boundary — bridge owns its protocol.
- Chat is off by default and requires explicit opt-in keys/config — v1 raises NotImplementedError on `enable_chat: true`.
- Unknown senders never see the full tool inventory — `visible_tools` filters per sender.
- `hermes mcp serve` is not provable from the `hermes-agent==0.13.0` wheel (`mcp_serve.py` missing) — demoted to spike-only.
- Local CI must not hit Almanac, Inspector, or Agentverse — NoopRegistrationPolicy plus inspector/manifest off in CI fixtures.
- Default `network` for the v1 bridge is **testnet**, not mainnet.
## Current top blockers (none, after triage)
The build session can start. All P0 questions are answered. The remaining items are recorded for the spike-during-build or post-ship follow-up.
