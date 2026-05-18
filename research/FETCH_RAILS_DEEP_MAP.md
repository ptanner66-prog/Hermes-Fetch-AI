# Fetch Rails Deep Map

Purpose: map the Fetch/uAgents/Agentverse/Almanac rails that Hermes Fetch AI can rely on without reimplementing them.

## One-line map

Hermes runs tools locally. uAgents carries signed agent messages. Agentverse supplies public registration, mailbox/proxy/hosted surfaces, adapters, and quotas. Almanac supplies decentralized registration/discovery semantics. The Agent Payment Protocol supplies payment negotiation message types, not automatic settlement in this repo.

## Rail 1: uAgents runtime and identity

Official source evidence:

- `raw/external-sources/uagents-pyproject.toml` from https://raw.githubusercontent.com/fetchai/uAgents/main/python/pyproject.toml records `uagents` version `0.24.2`.
- `raw/external-sources/uagents-github-agent.py` records the Agent constructor accepting `seed`, `endpoint`, `agentverse`, `mailbox`, `proxy`, `registration_policy`, `network`, metadata/readme/description/handle/avatar fields, and `publish_agent_details`.
- `raw/external-sources/fetch-uagent-communication.md` describes uAgent handlers such as `on_event`, `on_message`, `on_rest_get`, and `on_rest_post`.

Interpretation:

- A uAgent address/identity is a routing and protocol identity.
- It is not enough to authorize Hermes tool execution.
- Hermes must keep sender/tool policy local.

Hermes bridge use:

- `src/hermes_fetch_ai/uagent_app.py` builds a uAgent bridge and includes the direct protocol.
- `examples/local-direct.yaml` is the local no-Agentverse proof config.
- `examples/agentverse-mailbox-hermes.yaml` is the mailbox/Agentverse proof config and requires `UAGENT_SEED`.

## Rail 2: Agentverse registration and external agent exposure

Official source evidence:

- External uAgents / ACP registration: https://docs.agentverse.ai/documentation/launch-agents/external-agents/u-agents.md (`raw/external-sources/agentverse-external-uagents.md`). The cached doc says ACP registration can onboard uAgents into Agentverse/ASI:One and requires a live ACP-compatible uAgent, Agentverse API key, seed phrase, and reachable public endpoint.
- Register agent API: https://docs.agentverse.ai/api-reference/agents/register-agent.md (`raw/external-sources/agentverse-api-register-agent.md`). The API is `POST https://agentverse.ai/v2/agents`, with agent types including `uagent` and `a2a`, profile fields, and endpoints with URL/weight.
- Adapters overview: https://docs.agentverse.ai/documentation/launch-agents/external-agents/adapters-overview.md (`raw/external-sources/agentverse-adapters-overview.md`). Adapters implement Agent Chat Protocol for ASI:One-facing communication.

Interpretation:

- Agentverse can make a reachable agent discoverable and ASI:One-compatible.
- The repo cannot claim hosted proof until an operator supplies account/API key/seed/public endpoint and captures a live successful run.

Hermes bridge use:

- The bridge config keeps public endpoint/seed concerns explicit.
- Public docs should describe hosted proof as a runbook, not as already proven.

## Rail 3: Mailbox and proxy delivery

Official source evidence:

- Mailbox list API: https://docs.agentverse.ai/api-reference/agents/list-agent-mailbox-messages.md (`raw/external-sources/agentverse-api-list-mailbox.md`). It requires owner or agent attestation and validates transfer quotas.
- Mailbox submit API: https://docs.agentverse.ai/api-reference/agents/submit-mailbox-message.md (`raw/external-sources/agentverse-api-submit-mailbox.md`). It accepts signed/verified envelopes and stores them for target agents.
- Proxy submit API: https://docs.agentverse.ai/api-reference/agents/submit-proxy-message.md (`raw/external-sources/agentverse-api-submit-proxy.md`). It accepts signed/verified envelopes and redirects to registered endpoints.
- Readiness APIs are cached in `raw/external-sources/agentverse-api-mailbox-readiness.md` and `agentverse-api-proxy-readiness.md`.
- uAgents mailbox source is cached in `raw/external-sources/uagents-github-mailbox.py` and uses Agentverse API/challenge/signature behavior.

Interpretation:

- Mailbox mode is useful for agents that cannot expose a direct inbound public endpoint continuously.
- Proxy mode is useful when a registered endpoint can receive redirected envelopes.
- Both are delivery rails. Neither replaces Hermes local authorization.

Hermes bridge use:

- Mailbox demo should fail closed without `UAGENT_SEED`.
- A public endpoint/Agentverse account/API key remains operator-only.

## Rail 4: Almanac discovery/registration

Official source evidence:

- uAgents registration source `raw/external-sources/uagents-github-registration.py` checks whether an agent is registered, whether registration is near expiry, and whether endpoints/protocols changed. It checks balances/registration fees and distinguishes testnet and mainnet behavior.
- uAgents resolver source `raw/external-sources/uagents-github-resolver.py` can resolve Almanac/name service records and endpoints.

Interpretation:

- Almanac is a discovery/registration rail, not a trust oracle.
- Testnet/mainnet differences matter because registration can involve funds/fees.
- Operator approval is required before any mainnet/real-value action.

Hermes bridge use:

- V1 can document Almanac as a future discovery path while using local/mailbox proof first.
- Any live Almanac registration should be an operator-run proof step.

## Rail 5: Adapters and interoperability

Official source evidence:

- `raw/external-sources/uagents-adapter-pyproject.toml` records `uagents-adapter` version `0.6.2` and extras for MCP, A2A inbound/outbound, LangChain, and CrewAI.
- `raw/external-sources/uagents-adapter-readme.md` says the package provides LangChain, CrewAI, MCP Server, A2A outbound, and A2A inbound adapters.
- `raw/external-sources/uagents-adapter-mcp-readme.md` says the MCP Server Adapter bridges MCP servers and uAgents, supports Chat Protocol for ASI:One, and uses MCP tool discovery/execution.
- `raw/external-sources/agentverse-a2a-agents.md` describes surfacing A2A agents through Agentverse.

Interpretation:

- Fetch already has broad interoperability rails.
- Hermes should not wrap every adapter in v1.
- The safest v1 uses a direct, minimal protocol over a small Hermes tool subset; adapter use can remain future work if it preserves security boundaries.

## Rail 6: Payment negotiation primitives

Official source evidence:

- `raw/external-sources/uagents-core-payment.py` defines the official payment protocol models and `payment_protocol_spec` version `0.1.0`.
- The source interaction graph is `RequestPayment -> {CommitPayment, RejectPayment}` and `CommitPayment -> {CompletePayment, CancelPayment}`, with terminal `CompletePayment`, `CancelPayment`, and `RejectPayment`.
- `raw/external-sources/fetch-agent-payment-protocol.md` describes `Funds.payment_method` as rail-agnostic and lists common values such as `stripe`, `skyfire`, and `fet_direct`.

Interpretation:

- The source proves payment negotiation messages, not automatic settlement.
- The local repo implements dry-run only. Real settlement needs rail-specific verification and operator approval.

Hermes bridge use:

- Payment dry-run can gate tool execution until a synthetic payment flow is satisfied.
- Testnet/sandbox/real-value must remain separate proof levels.

## Rail 7: Quotas and subscriptions

Official source evidence:

- `raw/external-sources/agentverse-subscriptions-quotas.md` describes Agentverse subscription/quota concepts.
- `raw/external-sources/agentverse-api-list-mailbox.md` states mailbox listing increments bytes transferred and validates transfer quotas.

Interpretation:

- Hosted/Agentverse operation has economic/resource constraints beyond local code.
- Product docs should not promise unlimited hosted operations.

Hermes bridge use:

- Public docs should call out Agentverse account/quota requirements for hosted proof.
- Runtime should be rate-limited locally as well.

## Recommended v1 rail selection

Use now:

- uAgents identity/addressing as transport identity.
- Direct Hermes Fetch protocol over uAgents messages.
- Agentverse mailbox proof, operator-run.
- Official payment protocol models in dry-run.

Defer:

- Real marketplace listings.
- Wallet custody.
- Real FET/mainnet movement.
- Broad adapter fanout beyond minimal, source-backed bridge.
- Production hosted claims without operator-run evidence.
