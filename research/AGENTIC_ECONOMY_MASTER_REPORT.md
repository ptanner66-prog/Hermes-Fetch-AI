# Agentic Economy Master Report

Date: 2026-05-17
Scope: Hermes Fetch AI research-company completion pass using the existing source cache in `research/agentic-economy-research-company/`.

## Verdict

The evidence supports a narrow, practical thesis:

Hermes is the agent runtime. Fetch/uAgents/Agentverse/Almanac are the rails.

Hermes should not reimplement the agent economy. It should expose a small, policy-aware subset of local Hermes MCP/tool capability through uAgents-compatible protocols, while Fetch infrastructure supplies identity/addressing, discovery, registration, delivery surfaces, quota/subscription surfaces, and payment-negotiation primitives.

This is a strong bridge story, not a marketplace story. The safe v1 is a thin adapter with local proof, optional Agentverse mailbox/hosted proof, and dry-run/testnet-first payment negotiation. Real-value/mainnet movement remains explicitly operator-approved and out of automatic scope.

## Evidence base

Primary evidence is in `research/agentic-economy-research-company/source-ledger.md` and the raw cache under `research/agentic-economy-research-company/raw/external-sources/`.

Key official sources used:

- Agentverse external uAgent / ACP registration: https://docs.agentverse.ai/documentation/launch-agents/external-agents/u-agents.md (`raw/external-sources/agentverse-external-uagents.md`).
- Agentverse adapters overview: https://docs.agentverse.ai/documentation/launch-agents/external-agents/adapters-overview.md (`raw/external-sources/agentverse-adapters-overview.md`).
- Agentverse hosted agents: https://docs.agentverse.ai/documentation/create-agents/hosted-agents.md (`raw/external-sources/agentverse-hosted-agents.md`).
- Agentverse register/list/mailbox/proxy APIs: `raw/external-sources/agentverse-api-*.md`, including `POST https://agentverse.ai/v2/agents`, mailbox listing, mailbox submit, proxy submit, and readiness endpoints.
- uAgents package/source cache: `raw/external-sources/uagents-pyproject.toml`, `uagents-github-agent.py`, `uagents-github-registration.py`, `uagents-github-mailbox.py`, `uagents-github-resolver.py`.
- uAgents adapter package/source cache: `raw/external-sources/uagents-adapter-pyproject.toml`, `uagents-adapter-readme.md`, `uagents-adapter-mcp-readme.md`, `uagents-adapter-mcp-protocol.py`.
- Agent Payment Protocol: https://innovationlab.fetch.ai/resources/docs/agent-communication/agent-payment-protocol.md (`raw/external-sources/fetch-agent-payment-protocol.md`) and official source `raw/external-sources/uagents-core-payment.py`.
- Local implementation evidence: `src/hermes_fetch_ai/*.py`, `examples/*.yaml`, `tests/*.py`.
- Upstream Hermes reference evidence: `../hermes-agent-main/mcp_serve.py`, `toolsets.py`, `hermes_cli/plugins.py`, `acp_adapter/permissions.py`.

## What the rails provide

Fetch/uAgents/Agentverse/Almanac provide:

1. Agent identity and addressing.
   - uAgents initialize wallet/identity from seed/name (`raw/external-sources/uagents-github-agent.py`).
   - Agentverse registration APIs identify agents by address and metadata (`raw/external-sources/agentverse-api-register-agent.md`).
   - This is identity evidence, not trust or authorization.

2. Registration and discovery.
   - Agentverse has a register/update API (`POST https://agentverse.ai/v2/agents`) and listing metadata (`raw/external-sources/agentverse-api-register-agent.md`).
   - uAgents registration source checks Almanac state, endpoints, protocols, expiry, balance/fee, and testnet/mainnet behavior (`raw/external-sources/uagents-github-registration.py`).

3. Delivery surfaces.
   - External uAgent docs describe ACP registration and reachable public endpoint requirements (`raw/external-sources/agentverse-external-uagents.md`).
   - Agentverse mailbox APIs store signed/verified envelopes and require owner/agent attestation for listing (`raw/external-sources/agentverse-api-submit-mailbox.md`, `agentverse-api-list-mailbox.md`).
   - Proxy APIs submit signed/verified envelopes and redirect to registered endpoints (`raw/external-sources/agentverse-api-submit-proxy.md`).

4. Interoperability adapters.
   - Agentverse adapters implement Agent Chat Protocol for external agents (`raw/external-sources/agentverse-adapters-overview.md`).
   - uAgents adapter package supports LangChain, CrewAI, MCP Server, A2A outbound, and A2A inbound (`raw/external-sources/uagents-adapter-readme.md`, `uagents-adapter-pyproject.toml`).
   - MCP Server Adapter bridges MCP servers to uAgents and supports Chat Protocol for ASI:One (`raw/external-sources/uagents-adapter-mcp-readme.md`).

5. Economic primitives.
   - Agent Payment Protocol source defines `Funds`, `RequestPayment`, `CommitPayment`, `RejectPayment`, `CancelPayment`, `CompletePayment`, and `payment_protocol_spec` version `0.1.0` (`raw/external-sources/uagents-core-payment.py`).
   - Payment docs describe rail-agnostic `Funds.payment_method` and examples for `stripe`, `skyfire`, and `fet_direct` (`raw/external-sources/fetch-agent-payment-protocol.md`).
   - This proves message-level negotiation primitives; it does not prove real Hermes settlement.

## What Hermes provides

Hermes provides the local runtime and guardrails:

1. Tool execution and local MCP boundary.
   - Upstream Hermes MCP server uses FastMCP and stdio (`../hermes-agent-main/mcp_serve.py`).
   - Local bridge has fake/local/Hermes stdio shim modes (`src/hermes_fetch_ai/mcp_shim.py`).

2. Operator control and policy.
   - Config/policy files implement default-deny, public tool allowlists, sender allowlists, rate limits, output caps, and seed/payment gating (`src/hermes_fetch_ai/config.py`, `policy.py`, `direct_protocol.py`).
   - ACP permission reference denies on timeout/failure (`../hermes-agent-main/acp_adapter/permissions.py`).

3. Safety and observability.
   - Argument validation blocks schema failures, oversize args, local/private URL targets, and shell metacharacter hazards (`src/hermes_fetch_ai/arg_validator.py`).
   - Audit/redaction avoids raw args, raw outputs, full senders, seeds, tokens, and keys (`src/hermes_fetch_ai/audit.py`, `_redaction.py`).

4. Proof modes.
   - Local demo: `python -m hermes_fetch_ai.cli demo local`.
   - Mailbox demo: `python -m hermes_fetch_ai.cli demo mailbox --config examples/agentverse-mailbox-hermes.yaml --duration-seconds 5`, with `UAGENT_SEED` required and fail-closed without it.
   - Payment dry-run: `python -m hermes_fetch_ai.cli demo payment --config examples/payment-dry-run.yaml`.

## Proof levels

| Level | Meaning | Current status |
|---|---|---|
| Local proof | No Agentverse credentials or public endpoint. Hermes/uAgent bridge exercises local/fake backend and policy. | Implemented; verification command required. |
| Hosted proof | Agentverse account/API key/seed/public endpoint used to register/reach a live agent. | Operator-only until credentials and endpoint are supplied. Do not overclaim. |
| Dry-run payment | Official payment protocol models used with fake/dry-run transaction IDs; no funds move. | Implemented in local code; verification command required. |
| Testnet/sandbox | Uses non-production wallet/funds/sandbox payment rail. | Strategy only unless operator supplies testnet/sandbox resources. |
| Real-value/mainnet | Moves real funds or depends on live settlement. | Out of automatic scope; explicit operator approval required. |

## Security thesis

Identity is not trust.

Agentverse/uAgent identity and signatures can tell the bridge who a message claims to be from and whether an envelope is structurally valid. They do not decide which Hermes tools may run. Authorization remains local: allowlists, sender policy, argument validation, payment policy, audit, and operator approvals.

This is the main difference between a safe runtime bridge and a dangerous public tool tunnel.

## Product implication

V1 should not be a marketplace, wallet, exchange, or generic autonomous procurement system. V1 should be:

- a small uAgents-compatible bridge over carefully selected Hermes MCP tools;
- a public, source-backed local proof;
- an optional Agentverse mailbox/hosted proof runbook;
- a dry-run payment proof that demonstrates negotiation semantics without settlement;
- a clear operator-gated path for testnet/sandbox and real-value experiments.

## Main risks

1. Overclaiming Agentverse proof.
   - Source supports Agentverse registration/hosted/mailbox/proxy flows, but this repo still needs operator credentials/public endpoint for a hosted proof.

2. Treating identity as authorization.
   - Mitigated by local policy in `src/hermes_fetch_ai/policy.py` and `direct_protocol.py`.

3. Payment settlement confusion.
   - Official sources support payment protocol messages and rail identifiers, but this repo only implements dry-run payment. Real settlement is not verified.

4. Public tool overexposure.
   - Mitigated by v1 allowlists, default-deny, and explicit non-goals.

5. Secret leakage.
   - Mitigated by seed env requirement, config rejection of secret-shaped YAML, redaction/audit tests, and contamination scan command.

## Recommended decision

Proceed with an upstream PR package only if verification remains acceptable. The PR should be framed as documentation plus a thin, policy-aware proof bridge, not as a production payment or marketplace launch.

If verification fails on code/test issues, do not patch implementation in this pass; record file:line evidence and minimal fix in `research/PR_REVIEW_REPORT.md` and set the final run state honestly.
