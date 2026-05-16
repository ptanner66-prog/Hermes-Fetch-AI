# Public Positioning

Date accessed: 2026-05-16

## Tagline

Hermes Fetch AI connects Hermes Agent's local execution environment to Fetch.ai uAgents and Agentverse discovery.

## README opening draft

Hermes Fetch AI is a small bridge between Hermes Agent and Fetch.ai's uAgents ecosystem.

Hermes supplies the local agent runtime, tool execution, MCP integration, configuration, and operator boundaries. Fetch.ai supplies public agent identity, addressing, discovery, and agent-to-agent messaging through uAgents, Agentverse, and Almanac. This project connects the two through existing MCP/uAgents rails with explicit safety defaults.

The v1 goal is intentionally narrow: expose an allowlisted Hermes MCP surface as a uAgent, prove local direct uAgent calls, then optionally demonstrate Agentverse/Mailbox reachability. Remote uAgent identity is treated as identity and routing, not authorization.

## Safe claims

- Uses existing Fetch/uAgents and MCP primitives where possible.
- Exposes Hermes capabilities through an allowlisted bridge.
- Supports local direct uAgent demos.
- Can be configured for Agentverse/Mailbox once local proof passes.
- Keeps secrets in environment/config, not repository files.
- Treats unknown remote agents as untrusted.
- Separates standalone proof from a later narrow Hermes upstream PR.

## Claims to avoid

- Do not claim arbitrary Hermes tools are safe to expose publicly.
- Do not claim Agentverse discovery is authorization.
- Do not promise marketplace/payment/wallet capabilities.
- Do not overstate production hardening before public endpoint testing.
- Do not imply the bridge replaces Hermes or Fetch components.
- Do not include domain-specific examples or private project material.

## Short architecture summary

```text
Remote uAgent / Agentverse
  -> Fetch uAgents transport, address, protocol manifest
  -> Hermes Fetch AI bridge uAgent
  -> policy layer: sender/tool/schema/rate/timeout/audit
  -> Hermes MCP client shim
  -> Hermes MCP / local Hermes execution
  -> response through uAgents
```

## Later upstream PR framing

After the standalone repo works end-to-end, the reusable integration logic can be proposed upstream as an optional Hermes-native uAgents platform/plugin. The upstream PR should be narrow: optional dependency, platform/plugin registration, policy defaults, docs, and tests. Demo runner code, private research, and standalone packaging should stay out of Hermes core.

## One-paragraph CEO demo framing

"This proves Hermes can participate in the Fetch.ai agent network without reinventing the network. Fetch/uAgents handles agent identity, addressing, discovery, and message delivery. Hermes remains the local agent and execution environment. The bridge is intentionally thin and default-deny: external agent identities help route messages, but Hermes decides what, if anything, they are allowed to call."
