# Agentic Economy Thesis

## Thesis

Hermes is the agent runtime. Fetch/uAgents/Agentverse/Almanac are the rails.

This is a bridge thesis, not a hype thesis.

Hermes should not rebuild identity, registration, mailbox/proxy delivery, hosted-agent surfaces, adapters, discovery, quotas, or payment protocol primitives. Fetch already has those rails. Hermes should contribute the local runtime: MCP tools, operator approvals, policy, validation, audit, and redaction.

## Why this matters

Agent ecosystems need two different layers:

1. Rails
   - identity and addressing;
   - registration and discovery;
   - message delivery;
   - hosted surfaces;
   - adapter compatibility;
   - payment negotiation primitives.

2. Runtime
   - tool execution;
   - local context;
   - operator authority;
   - safety policy;
   - auditability;
   - redaction and approvals.

A safe agentic-economy bridge keeps those layers separate.

## Source-backed rails

Official source references:

- Agentverse external uAgents / ACP registration: https://docs.agentverse.ai/documentation/launch-agents/external-agents/u-agents.md
- Agentverse adapters overview: https://docs.agentverse.ai/documentation/launch-agents/external-agents/adapters-overview.md
- Agentverse hosted agents: https://docs.agentverse.ai/documentation/create-agents/hosted-agents.md
- Agentverse register-agent API: https://docs.agentverse.ai/api-reference/agents/register-agent.md
- uAgents repository: https://github.com/fetchai/uAgents
- Agent Payment Protocol guide: https://innovationlab.fetch.ai/resources/docs/agent-communication/agent-payment-protocol.md

## Design consequences

### Identity is not trust

A uAgent address, Agentverse listing, signed envelope, mailbox delivery, proxy delivery, or Almanac registration is identity/addressing evidence. It is not authorization to run Hermes tools.

Hermes Fetch AI keeps authorization local with allowlists, sender policy, validation, rate limits, output caps, audit, redaction, and operator approvals.

### V1 stays thin

V1 should prove:

- local bridge behavior;
- minimal public tool allowlist;
- Agentverse/hosted proof runbook boundaries;
- dry-run payment negotiation;
- no-secret and fail-closed posture.

V1 should not ship:

- marketplace sprawl;
- wallet custody;
- real-value payment movement;
- broad public access to Hermes tools.

### Proof levels are separate

- Local proof is not hosted proof.
- Hosted proof is not settlement proof.
- Dry-run payment is not real payment.
- Testnet/sandbox is not mainnet.
- Mainnet/real-value requires explicit operator approval.

## Practical product statement

Hermes Fetch AI lets a Hermes operator expose a small, reviewed, auditable tool surface through Fetch-compatible agent rails. It is valuable because it joins a real local runtime to real agent-network rails without erasing the operator boundary.
