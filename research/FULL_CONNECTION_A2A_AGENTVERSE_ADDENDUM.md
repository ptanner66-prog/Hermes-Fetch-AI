# Full Connection A2A Agentverse Addendum

Operator note, 2026-05-16:
The Agentverse A2A external-agent path is a serious candidate for the Hermes-native PR strategy. Do not reduce the integration to mailbox-only or uAgent-only before evaluating this.

Source:
https://docs.agentverse.ai/documentation/launch-agents/external-agents/a-2-a-agents

## What the source says

- Agent-to-Agent (A2A) is a protocol for direct, structured communication between autonomous agents, regardless of the framework used to build them.
- Agentverse can surface an external agent so users and other agents can interact with it, improving discoverability and monetization in the broader ASI:One ecosystem.
- Agentverse requires consistent interoperability; the Chat Protocol is one route, but the latest `uagents-core` package adds an A2A adapter that reduces custom chat-protocol integration work.
- The adapter connects to an existing agent endpoint and relays messages between Agentverse and the application.
- A public endpoint is required for the external agent path because Agentverse verifies availability and exchanges messages with the agent.
- The example uses an A2A `AgentCard` with:
  - name
  - description
  - url
  - version
  - input/output modes
  - capabilities
  - skills
  - optional authenticated extended card
- The Agentverse UI provides a generated snippet like:
  `from uagents_core.adapters.a2a import agentverse_sdk`
  `agentverse_sdk.init("<agentverse connection URL>")`
- Agentverse then evaluates registration, exposes dashboard data, README, handle, rating, Testing tab, Chat with Agent, and ASI:One chat routing.

## Required evaluation

Before final acceptance, Hermes must evaluate and document whether the upstream PR should use one or both paths:

1. uAgents/MCP path:
   - Best for native agent-to-agent protocol messages, tool-call schemas, Almanac manifest digests, direct remote uAgent calls, mailbox/proxy/endpoint modes, and payment protocol composition.

2. A2A external-agent path:
   - Best for connecting an existing Hermes HTTP/A2A-compatible endpoint into Agentverse with minimal code, Agent Card metadata, ASI:One reachability, Agentverse testing, and discovery/monetization surfaces.

3. Hybrid:
   - Hermes exposes a narrow native uAgent/MCP bridge for structured tool work and a separate A2A/Agent Card surface for Agentverse/ASI:One interoperability.

## Implementation implications

The final repo must answer:

- Does `uagents-core==0.4.4` in this repo contain `uagents_core.adapters.a2a.agentverse_sdk`?
- Does the current version require the separate `a2a` package?
- Can Hermes Fetch AI generate an A2A Agent Card from the same allowed Hermes tool policy?
- Can the A2A path stay default-off and avoid exposing side-effecting Hermes tools?
- Can a local A2A endpoint be tested without Agentverse secrets?
- What exact operator-owned Agentverse Launch Agent steps remain?
- Does this become the cleaner upstream Hermes PR than a direct uAgents command, or should it be an optional second command?

## Hard acceptance gate

The run is not Teknium-ready unless `research/FETCH_FULL_CONNECTION_MAP.md` or `research/UPSTREAM_PR_EXECUTION_PLAN.md` explicitly includes an A2A decision:

- recommended now
- recommended later
- rejected with source-backed reasons

If recommended now, add the minimum safe code/tests/docs needed for a dry-run/local A2A Agent Card or endpoint proof. If recommended later, document the exact v2 scope. If rejected, explain why the native uAgents/MCP route is superior for Hermes.
