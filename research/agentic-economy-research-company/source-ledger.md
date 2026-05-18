# Agentic Economy Research Company Source Ledger

Run directory: `research/agentic-economy-research-company/`
Status: populated from existing local source cache only; no new external collection in this continuation pass.
Route: ChatGPT-only, model `gpt-5.5`, provider `openai-codex`, API mode `codex_responses`.

## Use rules

- Evidence in this ledger is source-backed, not marketing inference.
- Agentverse/uAgent addresses, signatures, and registration are treated as identity/addressing evidence, not authorization or trust.
- Hosted proof, dry-run payment, testnet/sandbox, and real-value/mainnet are separate evidence levels.
- No secrets, seed phrases, API keys, wallet private keys, client secrets, or `.env` content were inspected or recorded.

## Primary assignment and prior run

| Source | Local cache / file | Evidence used | Notes |
|---|---|---|---|
| Assignment prompt | `research/AGENTIC_ECONOMY_RESEARCH_COMPANY_PROMPT.md` | Required artifacts, required public docs, route constraints, verification commands, and content standards. | Operator authority allowed edits only under `research/**`, `docs/**`, and `README.md` in this pass. |
| Prior run log | `research/agentic-economy-research-company-run.log` | The prior run completed preflight/source collection and produced the thesis that Hermes is the runtime while Fetch/uAgents/Agentverse/Almanac are rails. It did not write final artifacts or run verification. | Continuation pass uses this as handoff, not as substitute for source citations. |
| Initial git snapshots | `research/agentic-economy-research-company/raw/initial-git-status-short-branch.txt`, `raw/initial-git-diff-stat.txt`, `raw/git-log-oneline-5.txt`, `raw/git-ls-files.txt` | Pre-continuation repository state. | Final state must be verified separately. |

## Official Fetch / Agentverse / uAgents sources cached locally

| Topic | Official URL | Local cache | Key evidence used | Evidence level |
|---|---|---|---|---|
| Agentverse external uAgents / ACP registration | https://docs.agentverse.ai/documentation/launch-agents/external-agents/u-agents.md | `raw/external-sources/agentverse-external-uagents.md` | ACP registration can onboard uAgents into Agentverse/ASI:One; it requires an ACP-compatible uAgent, Agentverse API key, seed phrase, and a reachable public endpoint for availability/message exchange. | Official doc cache; usable. |
| Agentverse adapters overview | https://docs.agentverse.ai/documentation/launch-agents/external-agents/adapters-overview.md | `raw/external-sources/agentverse-adapters-overview.md` | Adapters are bridges implementing Agent Chat Protocol so external agents can expose a public interface and communicate through ASI:One. | Official doc cache; usable. |
| A2A agents on Agentverse | https://docs.agentverse.ai/documentation/launch-agents/external-agents/a-2-a-agents.md | `raw/external-sources/agentverse-a2a-agents.md` | Agentverse can surface A2A agents; A2A adapter bridges existing A2A endpoints into Agentverse/Chat Protocol. | Official doc cache; usable. |
| Hosted Agents | https://docs.agentverse.ai/documentation/create-agents/hosted-agents.md | `raw/external-sources/agentverse-hosted-agents.md` | Hosted Agents are cloud-managed Agentverse agents; they reset global variables after each call and need Agent Storage for stateful behavior. | Official doc cache; usable. |
| Subscriptions and quotas | https://docs.agentverse.ai/documentation/subscriptions-and-quotas.md | `raw/external-sources/agentverse-subscriptions-quotas.md` | Agentverse has subscription/quota constraints including transfer quota concepts; mailbox listing API also increments bytes transferred and validates quotas. | Official doc cache; usable. |
| Agentverse register-agent API | https://docs.agentverse.ai/api-reference/agents/register-agent.md | `raw/external-sources/agentverse-api-register-agent.md` | `POST https://agentverse.ai/v2/agents` registers/updates an agent listing; agent type enum includes `uagent` and `a2a`; endpoint entries include URL and weight. | Official API cache; usable. |
| Agentverse mailbox list API | https://docs.agentverse.ai/api-reference/agents/list-agent-mailbox-messages.md | `raw/external-sources/agentverse-api-list-mailbox.md` | Mailbox listing requires owner or agent attestation and validates transfer quotas. | Official API cache; usable. |
| Agentverse submit mailbox API | https://docs.agentverse.ai/api-reference/agents/submit-mailbox-message.md | `raw/external-sources/agentverse-api-submit-mailbox.md` | Mailbox submit accepts signed/verified envelopes and stores them for the target agent. | Official API cache; usable. |
| Agentverse submit proxy API | https://docs.agentverse.ai/api-reference/agents/submit-proxy-message.md | `raw/external-sources/agentverse-api-submit-proxy.md` | Proxy submit accepts signed/verified envelopes and redirects to the registered endpoint. | Official API cache; usable. |
| Agentverse mailbox/proxy readiness APIs | https://docs.agentverse.ai/api-reference/agents/mailbox-readiness.md, https://docs.agentverse.ai/api-reference/agents/proxy-readiness.md | `raw/external-sources/agentverse-api-mailbox-readiness.md`, `agentverse-api-proxy-readiness.md` | Readiness checks are part of proving mailbox/proxy reachability. | Official API cache; usable. |
| uAgents adapter guide | https://innovationlab.fetch.ai/resources/docs/agent-creation/uagents-adapter-guide.md | `raw/external-sources/fetch-uagents-adapter-guide.md` | uAgents adapters connect uAgents to other agentic frameworks. | Official doc cache; usable. |
| uAgents adapter README | https://raw.githubusercontent.com/fetchai/uAgents/main/python/uagents-adapter/README.md | `raw/external-sources/uagents-adapter-readme.md` | Adapter package includes LangChain, CrewAI, MCP Server, A2A outbound, and A2A inbound adapters; examples show mailbox registration and Agentverse token usage. | Official source cache; usable. |
| MCP Server Adapter | https://raw.githubusercontent.com/fetchai/uAgents/main/python/uagents-adapter/README.md plus MCP adapter docs | `raw/external-sources/uagents-adapter-mcp-readme.md`, `uagents-adapter-mcp-protocol.py` | MCP Server Adapter bridges MCP servers to uAgents, supports Chat Protocol for ASI:One, and exposes MCP tool discovery/execution. MCP tools should carry detailed docstrings. | Official source/cache; usable. |
| uAgents package version/deps | https://raw.githubusercontent.com/fetchai/uAgents/main/python/pyproject.toml | `raw/external-sources/uagents-pyproject.toml` | `uagents` version `0.24.2`, Python `>=3.10,<4.0`, depends on `uagents-core`, `pydantic`, `uvicorn`, `aiohttp`, `cosmpy`. | Official source cache; usable. |
| uAgents adapter package version/deps | https://raw.githubusercontent.com/fetchai/uAgents/main/python/uagents-adapter/pyproject.toml | `raw/external-sources/uagents-adapter-pyproject.toml` | `uagents-adapter` version `0.6.2`, extras include `mcp`, `a2a-inbound`, `a2a-outbound`, `langchain`, `crewai`. | Official source cache; usable. |
| uAgent communication | https://innovationlab.fetch.ai/resources/docs/agent-communication/uagent-uagent-communication.md | `raw/external-sources/fetch-uagent-communication.md` | uAgents communication is handler/protocol oriented (`on_event`, `on_message`, REST handlers). | Official doc cache; usable. |
| uAgent creation | https://innovationlab.fetch.ai/resources/docs/agent-creation/create-a-uagent.md | `raw/external-sources/fetch-uagent-creation.md` | Baseline agent creation concepts and uAgent runtime. | Official doc cache; usable. |
| Agent Payment Protocol guide | https://innovationlab.fetch.ai/resources/docs/agent-communication/agent-payment-protocol.md | `raw/external-sources/fetch-agent-payment-protocol.md` | Payment protocol is rail-agnostic through `Funds.payment_method`; examples discuss `stripe`, `skyfire`, and `fet_direct`; flow is RequestPayment -> CommitPayment/RejectPayment -> CompletePayment/CancelPayment. | Official doc cache; usable, but examples are not proof of Hermes real settlement. |
| uAgents core payment source | https://raw.githubusercontent.com/fetchai/uAgents/main/python/uagents-core/uagents_core/contrib/protocols/payment/__init__.py | `raw/external-sources/uagents-core-payment.py` | Source defines `Funds`, `RequestPayment`, `RejectPayment`, `CommitPayment`, `CancelPayment`, `CompletePayment`, `payment_protocol_spec` version `0.1.0`; source default `payment_method` is `fet_direct`. | Official source cache; strongest payment model evidence. |
| uAgents registration source | https://raw.githubusercontent.com/fetchai/uAgents/main/python/src/uagents/registration.py | `raw/external-sources/uagents-github-registration.py` | Almanac registration checks registration state/endpoints/protocols, requires balance/fee, distinguishes testnet and mainnet, and signs registration. | Official source cache; usable. |
| uAgents agent source | https://raw.githubusercontent.com/fetchai/uAgents/main/python/src/uagents/agent.py | `raw/external-sources/uagents-github-agent.py` | Agent constructor accepts seed, endpoint, agentverse, mailbox, proxy, registration policy, network, metadata/readme/description/handle/avatar, and `publish_agent_details`; identity is initialized from seed/name. | Official source cache; usable. |
| uAgents mailbox source | https://raw.githubusercontent.com/fetchai/uAgents/main/python/src/uagents/mailbox.py | `raw/external-sources/uagents-github-mailbox.py` | Mailbox uses Agentverse APIs and identity proof/challenge/signature behavior. | Official source cache; usable. |
| uAgents resolver source | https://raw.githubusercontent.com/fetchai/uAgents/main/python/src/uagents/resolver.py | `raw/external-sources/uagents-github-resolver.py` | Resolver can query Almanac/name service records and endpoints. | Official source cache; usable. |

## Local Hermes Fetch AI implementation sources

| Area | Local file | Evidence used | Notes |
|---|---|---|---|
| Config and seed policy | `src/hermes_fetch_ai/config.py` | Config has explicit modes, env seed resolution for mailbox, dry-run payment config, secret-shaped YAML rejection, `real_operator_approved` operator stop. | Implementation was inspected only; not patched in this pass. |
| Policy and direct protocol | `src/hermes_fetch_ai/policy.py`, `src/hermes_fetch_ai/direct_protocol.py` | Default-deny tool policy, public/allowed senders, rate limits, output caps, audit before/around send. | Supports "identity is not trust" posture. |
| Argument validation | `src/hermes_fetch_ai/arg_validator.py` | Schema validation, size limits, unsafe URL/local/private host checks, shell metacharacter checks. | Supports security model. |
| Audit and redaction | `src/hermes_fetch_ai/audit.py`, `src/hermes_fetch_ai/_redaction.py` | Audit events avoid raw args/outputs and redact secret-shaped values/full senders. | Supports no-secret public posture. |
| MCP shim | `src/hermes_fetch_ai/mcp_shim.py` | Fake/local/Hermes stdio modes, tool listing/call normalization. | Hermes runtime boundary remains local. |
| uAgent app | `src/hermes_fetch_ai/uagent_app.py` | Builds uAgent with mailbox/proxy/local modes, includes protocol, runs mailbox child process with readiness and failure handling. | Hosted/Agentverse proof still needs operator credentials/public endpoint. |
| Payments | `src/hermes_fetch_ai/payments.py`, `src/hermes_fetch_ai/payment_policy.py`, `src/hermes_fetch_ai/payment_protocol.py` | Dry-run request/commit/complete/cancel behavior using official uAgents-core models. | Not real settlement; no wallet custody. |
| CLI | `src/hermes_fetch_ai/cli.py` | `doctor`, local demo, Hermes demo, mailbox demo, payment dry-run demo, contamination scan. | Verification commands exercise this. |
| Examples | `examples/local-direct.yaml`, `examples/agentverse-mailbox-hermes.yaml`, `examples/payment-dry-run.yaml`, `examples/hermes-stdio-env.yaml` | Concrete local, mailbox, and payment dry-run modes. | Examples must not include real secrets. |
| Tests | `tests/test_direct_protocol_policy.py`, `tests/test_mailbox_startup.py`, `tests/test_payment_demo.py`, `tests/test_payment_policy.py`, `tests/test_config.py`, `tests/test_contamination.py` | Tests cover policy denial, validation, audit redaction, mailbox seed fail-closed, dry-run payment, and contamination checks. | Final verification records exact outcomes. |

## Upstream Hermes reference sources

| Area | Upstream file | Evidence used | Notes |
|---|---|---|---|
| Hermes MCP server | `../hermes-agent-main/mcp_serve.py` | Upstream Hermes exposes an MCP server using FastMCP and stdio (`run_stdio_async`), with messaging tools such as conversation/message read, attachment fetch, event poll/wait, message send, and permission handling. | Reference only; no upstream changes made in this pass. |
| Hermes toolsets | `../hermes-agent-main/toolsets.py` | Core toolsets include web, terminal/process, file, vision/image, skills, browser, TTS, todo/memory/session search, clarify, delegation, cron, messaging, Home Assistant, kanban. | Used to shape allowlist strategy; not all tools should be public. |
| Hermes plugins | `../hermes-agent-main/hermes_cli/plugins.py` | Plugin hooks include `pre_tool_call`, `post_tool_call`, output/result transforms, LLM/API hooks, session hooks; project plugins are opt-in through `HERMES_ENABLE_PROJECT_PLUGINS`. | Supports future integration points; not a security boundary by itself. |
| ACP permissions | `../hermes-agent-main/acp_adapter/permissions.py` | Permission bridge maps allow/reject decisions to Hermes approval results and denies on timeout/failure. | Supports operator approval boundary. |

## Gaps deliberately not filled by inference

- No hosted Agentverse proof was claimed without an operator-run Agentverse account/API key/seed/public endpoint flow.
- No real FET/mainnet or real Stripe/Skyfire settlement was claimed.
- No wallet custody model was invented.
- No legal, compliance, or production go-live advice is final; these artifacts are technical research and PR packaging support.
