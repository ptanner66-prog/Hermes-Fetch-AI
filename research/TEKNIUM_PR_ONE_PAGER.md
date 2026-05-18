# Teknium PR One-Pager

Updated: 2026-05-17T03:35:34Z

## One-line pitch

Hermes can expose a narrow, policy-filtered MCP tool surface over Fetch/uAgents identity, addressing, mailbox/discovery, and payment negotiation rails, without turning Hermes into a new network agent framework and without turning Fetch into a local execution agent.

## Why this is interesting

Fetch already has the agent network rails:

- uAgent identity and addresses;
- signed message routing;
- endpoint/mailbox/proxy transport modes;
- Agentverse and Almanac discovery/manifest surfaces;
- payment protocol message models and agentic commerce context.

Hermes already has the local operator rails:

- local tools and MCP server;
- skills/plugins/config/logging;
- local execution and operator approval boundaries;
- terminal-first developer workflow.

This repo is the small missing membrane:

- map uAgents MCP protocol messages to Hermes MCP stdio;
- filter tools by sender;
- deny unsafe tools by default;
- validate arguments before local execution;
- redact and reduce audit logs;
- prove payment negotiation without wallet custody or settlement.

## What is proven now

Local proof, no hosted account required:

- `77 passed in 17.94s`
- Ruff green
- Mypy green
- Contamination scan green
- fake local uAgents dispatcher demo returns `echo result: hello`
- real Hermes stdio backend probe reports `backend: ok: 10 tools`
- Hermes stdio bridge demo calls `conversations_list` and returns `{"count": 0, "conversations": []}` through the bridge
- payment dry-run demo returns `CompletePayment` and explicitly performs no settlement
- mailbox config fails closed when no operator seed is supplied

## What is intentionally not claimed

- No hosted Agentverse mailbox transcript yet.
- No remote Agentverse Inspector proof yet.
- No wallet custody or settlement.
- No mainnet transaction.
- No A2A external-agent bridge in PR one.
- No replacement for Hermes tools, prompts, or plugins.
- No replacement for Fetch discovery/identity/payment rails.

## Suggested upstream PR one

Title:

`feat(plugins): add optional Fetch uAgents bridge for Hermes MCP tools`

Shape:

- default-off Hermes plugin or small CLI command;
- optional uAgents dependencies;
- local stdio command path to `hermes mcp serve`;
- public tool allowlist default empty or read-only sample;
- deny side-effecting send/approval tools by default;
- mailbox/Agentverse docs as operator checklist;
- payment dry-run note/test only, no settlement;
- no A2A in the first patch unless requested.

## Why this PR should be reviewable

It does not require a new agent framework, a new wallet UX, a new marketplace, or broad Hermes core changes. The first patch can be mostly:

- plugin metadata;
- command wiring;
- optional dependency checks;
- config defaults;
- tests;
- docs.

The standalone repo already proves the hard parts that matter for safety:

- policy before invocation;
- filtered inventory;
- subprocess isolation;
- redacted audit;
- no hosted or funded side effect in CI.

## Ask

Review the bridge as a thin connection layer between Fetch/uAgents and Hermes MCP, not as a competing agent platform. If the direction is acceptable, confirm whether the first upstream contribution should be:

1. bundled Hermes plugin;
2. external plugin with docs link;
3. small core CLI command plus optional dependency;
4. docs-only pointer first, code second.

## Operator-owned follow-up proof

After review direction, the next evidence pass should be an operator-run hosted proof:

1. set seed only in the operator shell;
2. start mailbox bridge;
3. link Agentverse mailbox/agent entry;
4. send `ListTools` and `CallTool(conversations_list)` from a remote uAgent;
5. record non-secret transcript and manifest/digest evidence.
