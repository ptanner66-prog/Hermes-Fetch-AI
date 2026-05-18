# Agentverse Hosted Proof

This page describes what a hosted or Agentverse-facing proof would mean for Hermes Fetch AI.

It does not claim that hosted proof has already completed.

For runnable local commands, use `docs/demo.md`. Keep any live Agentverse evidence outside public docs unless it has been sanitized.

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
- A2A Protocol registration/setup in Agentverse.
- Reachable public endpoint, agent card, mailbox, or proxy setup depending on the A2A path Agentverse requires.
- Awareness of Agentverse quotas/subscriptions.
- Captured proof output with secrets redacted.

The intended hosted path is A2A-first. In Agentverse, choose **A2A Protocol** for the agent stack. Agent Chat Protocol is not the target product path for this bridge.

Mailbox/Inspector remains useful as a supporting transport and fail-closed safety check, but it is not the strategic proof. The proof that matters for Teknium is Hermes as the local runtime connected into Fetch/Agentverse A2A rails, with the bridge exposing only a minimal policy-controlled surface.

Official source references:

- A2A Protocol specification: https://a2a-protocol.org/latest/specification/
- External uAgent registration: https://docs.agentverse.ai/documentation/launch-agents/external-agents/u-agents
- Adapters overview: https://docs.agentverse.ai/documentation/launch-agents/external-agents/adapters-overview.md
- Hosted Agents: https://docs.agentverse.ai/documentation/create-agents/hosted-agents.md
- Register Agent API: https://docs.agentverse.ai/api-reference/agents/register-agent.md
- Mailbox listing API: https://docs.agentverse.ai/api-reference/agents/list-agent-mailbox-messages.md
- Mailbox submit API: https://docs.agentverse.ai/api-reference/agents/submit-mailbox-message
- Proxy submit API: https://docs.agentverse.ai/api-reference/agents/submit-proxy-message.md

## A2A-first hosted proof

The operator-facing Agentverse flow should start with:

1. Sign in to Agentverse.
2. Create or register an agent.
3. Choose **A2A Protocol** as the stack/protocol.
4. Capture the required A2A metadata fields Agentverse asks for, such as endpoint, agent card, protocol digest, handle, or registration identifier.
5. Start from an empty/minimal public tool policy.
6. Prove discovery/registration first.
7. Prove a denied or no-op/minimal call path before exposing any Hermes-backed tool.

Do not claim the A2A hosted proof is complete until the operator records the actual Agentverse result, the bridge/uAgent identifier, sanitized transcript or registration evidence, and the final tool policy used.

## Supporting mailbox proof modes

The mailbox configs are supporting evidence only. They prove startup and fail-closed behavior around uAgent seed handling and remote-reachable mode. They are not the main Teknium story.

Mailbox linking smoke uses:

```bash
python -m hermes_fetch_ai.cli serve --config examples/agentverse-mailbox.yaml
```

That config uses fake MCP, Inspector enabled, and an empty public tool policy. It is for transport/linking smoke only, not the A2A proof and not Hermes backend proof.

Real Hermes mailbox smoke uses:

```bash
python -m hermes_fetch_ai.cli serve --config examples/agentverse-mailbox-hermes.yaml
```

Short startup smoke can use:

```bash
python -m hermes_fetch_ai.cli demo mailbox --config examples/agentverse-mailbox-hermes.yaml --duration-seconds 5
```

With no `UAGENT_SEED`, this should fail closed. That negative proof is part of the safety model.

With operator-supplied seed material and Agentverse setup, `serve` can support remote mailbox traffic. Do not commit the seed or paste it into docs. Treat this as transport evidence unless it is explicitly part of the A2A setup Agentverse requires.

Before running a positive hosted proof, keep `policy.public_tools` empty unless a specific remote sender and one low-risk tool have been reviewed. Remote identity is routing and attribution evidence, not authorization.

## Evidence to record privately

Hosted evidence should be captured in a private operator note first, then copied into public docs only after review. Record:

- command names and exit codes;
- bridge/uAgent address or redacted Agentverse identifier;
- remote sender address if safe to publish;
- sanitized request and response transcript;
- proof that `policy.public_tools` stayed empty or minimal;
- proof that denied tools stayed denied;
- confirmation that missing `UAGENT_SEED` still fails closed;
- confirmation that the Agentverse stack/protocol selected was A2A, if the proof is being used for the Teknium A2A story;
- confirmation that no seed, API, mailbox, wallet, or payment credential appeared in logs, docs, commits, or screenshots.

## External A2A/public endpoint proof

If the proof uses A2A registration or a public endpoint rather than mailbox delivery, record:

- endpoint URL or redacted deployment identifier;
- whether the endpoint is tunnel, staging, or production;
- which Agentverse A2A registration/API action was used;
- any agent card or protocol metadata Agentverse required, with secrets redacted;
- resulting agent address/handle if safe to publish;
- exact command output with credentials redacted;
- whether any quotas or subscription constraints applied.

If `public_base_url` is not loopback (`127.0.0.1` or `localhost`), set `a2a.require_bearer_token: true` and provide `HERMES_FETCH_A2A_BEARER_TOKEN` only in the operator shell before exposing the endpoint.

## What not to claim

Do not claim:

- Agentverse mailbox proof is complete from local-only runs.
- A2A hosted proof is complete from local-only runs.
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
