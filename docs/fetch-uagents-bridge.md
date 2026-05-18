# Hermes Fetch uAgents Bridge

Hermes Fetch AI is a thin bridge between the Hermes local runtime and Fetch.ai uAgents rails.

The intended split is simple:

- Hermes supplies local tool execution, MCP integration, operator approvals, policy, redaction, and audit.
- Fetch/uAgents/Agentverse/Almanac supply identity/addressing, agent registration/discovery, mailbox/proxy delivery, hosted-agent surfaces, adapters, and payment protocol primitives.

This project does not create a new agent framework, marketplace, wallet, or payment processor.

## What the bridge does

The bridge exposes a small, policy-controlled Hermes tool surface through a uAgent-compatible runtime.

A safe v1 flow is:

1. A caller asks which tools are visible.
2. Hermes Fetch AI returns only allowlisted public tools.
3. The caller requests a tool call with JSON arguments.
4. The bridge validates sender policy, tool allowlist, argument schema, argument size, URL targets, and output limits.
5. Only then does the bridge call the local Hermes/MCP backend.
6. The bridge records redacted audit metadata.

Sender identity helps route and attribute messages. It does not authorize tool execution by itself.

## Proof levels

| Level | Meaning |
|---|---|
| Local proof | Run the bridge and demo tools with no Agentverse credentials. |
| Hosted or mailbox proof | Operator supplies Agentverse account/API key/seed/public endpoint or mailbox setup. |
| Dry-run payment | Use official payment protocol models without moving funds. |
| Testnet/sandbox | Operator-approved non-production payment or registration experiment. |
| Real-value/mainnet | Explicit operator-approved production settlement or mainnet action. |

Do not treat a local proof as hosted proof. Do not treat dry-run payment as settlement.

## Safe default posture

- Default-deny tool calls.
- Minimal public allowlist.
- No wallet custody.
- No real-value FET transfer without explicit operator approval.
- No secrets in config files or docs.
- Mailbox/Agentverse seed comes from environment, not repo files.
- Audit output should avoid raw args, raw outputs, full sender addresses, seeds, tokens, and keys.

## Run local proof

From the repo root:

```bash
python -m hermes_fetch_ai.cli doctor
python -m hermes_fetch_ai.cli demo local
```

Expected local proof behavior:

- The bridge starts with a local/fake backend.
- A small public tool set is visible.
- The demo tool call succeeds.
- Audit events are recorded without secrets.

## Run payment dry-run proof

```bash
python -m hermes_fetch_ai.cli demo payment --config examples/payment-dry-run.yaml
```

This demonstrates protocol-level payment negotiation only. No real funds move.

## Source-backed rail claims

Official sources used by the research package include:

- Agentverse external uAgents / ACP registration: https://docs.agentverse.ai/documentation/launch-agents/external-agents/u-agents
- Agentverse adapters overview: https://docs.agentverse.ai/documentation/launch-agents/external-agents/adapters-overview.md
- Agentverse hosted agents: https://docs.agentverse.ai/documentation/create-agents/hosted-agents.md
- Agentverse register agent API: https://docs.agentverse.ai/api-reference/agents/register-agent.md
- Agentverse mailbox API: https://docs.agentverse.ai/api-reference/agents/list-agent-mailbox-messages.md
- uAgents repository: https://github.com/fetchai/uAgents
- Agent Payment Protocol guide: https://uagents.fetch.ai/docs/guides/agent-payment-protocol

See also:

- `docs/agentverse-hosted-proof.md`
- `docs/payment-rails.md`
- `docs/agentic-economy-thesis.md`
