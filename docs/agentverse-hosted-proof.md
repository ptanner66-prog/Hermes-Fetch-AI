# Agentverse Hosted Proof

This page describes what a hosted or Agentverse-facing proof would mean for Hermes Fetch AI.

It does not claim that hosted proof has already completed.

For the live operator sequence, use `docs/agentverse-operator-handoff.md`.

## What is already locally provable

A local proof can show:

- Hermes Fetch AI can start a local bridge.
- A small public tool allowlist can be listed.
- A local demo tool can be called.
- Policy, validation, redaction, and audit behavior run before/around tool execution.
- Mailbox mode fails closed if `UAGENT_SEED` is not supplied.

Local proof does not require Agentverse credentials.

## What hosted proof requires

A real Agentverse-facing proof requires operator-owned resources:

- Agentverse account.
- Agentverse API key or required account authorization.
- Operator-supplied uAgent seed through environment, not config files.
- Reachable public endpoint, mailbox, or proxy setup depending on mode.
- Awareness of Agentverse quotas/subscriptions.
- Captured proof output with secrets redacted.

The recommended first live path is mailbox/Inspector linking, followed by the real Hermes mailbox bridge. External ACP registration is a later public-endpoint proof because it requires an ACP-compatible uAgent, API credential, seed material, and a reachable endpoint.

Official source references:

- External uAgent / ACP registration: https://docs.agentverse.ai/documentation/launch-agents/external-agents/u-agents
- Adapters overview: https://docs.agentverse.ai/documentation/launch-agents/external-agents/adapters-overview.md
- Hosted Agents: https://docs.agentverse.ai/documentation/create-agents/hosted-agents.md
- Register Agent API: https://docs.agentverse.ai/api-reference/agents/register-agent.md
- Mailbox listing API: https://docs.agentverse.ai/api-reference/agents/list-agent-mailbox-messages.md
- Mailbox submit API: https://docs.agentverse.ai/api-reference/agents/submit-mailbox-message
- Proxy submit API: https://docs.agentverse.ai/api-reference/agents/submit-proxy-message.md

## Mailbox proof modes

First linking uses:

```bash
python -m hermes_fetch_ai.cli serve --config examples/agentverse-mailbox.yaml
```

That config uses fake MCP, Inspector enabled, and an empty public tool policy. It is for Agentverse mailbox linking only, not Hermes proof.

Real Hermes proof uses:

```bash
python -m hermes_fetch_ai.cli serve --config examples/agentverse-mailbox-hermes.yaml
```

Short startup smoke can use:

```bash
python -m hermes_fetch_ai.cli demo mailbox --config examples/agentverse-mailbox-hermes.yaml --duration-seconds 5
```

With no `UAGENT_SEED`, this should fail closed. That negative proof is part of the safety model.

With operator-supplied seed material and Agentverse setup, `serve` is the live proof mode for remote mailbox traffic. Do not commit the seed or paste it into docs.

Before running a positive hosted proof, keep `policy.public_tools` empty unless a specific remote sender and one low-risk tool have been reviewed. Remote identity is routing and attribution evidence, not authorization.

## External ACP/public endpoint proof

If the proof uses external ACP registration or a public endpoint rather than mailbox delivery, record:

- endpoint URL or redacted deployment identifier;
- whether the endpoint is tunnel, staging, or production;
- which Agentverse registration/API action was used;
- resulting agent address/handle if safe to publish;
- exact command output with credentials redacted;
- whether any quotas or subscription constraints applied.

## What not to claim

Do not claim:

- Agentverse mailbox proof is complete from local-only runs.
- Agentverse identity authorizes Hermes tools.
- Public endpoint availability means arbitrary tools are safe.
- Hosted proof includes payment settlement.
- Seed/API credentials can be stored in repo config.

## Acceptance criteria for hosted proof

A hosted proof is acceptable only when all are true:

1. Operator explicitly supplies required credentials/resources.
2. No secrets are written to repo files or public docs.
3. Agent identity/address is captured without treating it as authorization.
4. Tool allowlist remains minimal.
5. The proof records exact commands and outcomes.
6. The no-seed negative test remains fail-closed.
