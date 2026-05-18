# Fetch Full Connection Map

Status: full hosted connection is not proven in this run. The standalone proof now covers the local native uAgents/MCP path, Hermes stdio MCP path, mailbox startup command path, and default-off payment dry-run negotiation. Hosted discovery/linking remains operator-owned.

## Source-backed surfaces

Source access checks succeeded on 2026-05-16:

- Agentverse external A2A page returned HTTP 200: https://docs.agentverse.ai/documentation/launch-agents/external-agents/a-2-a-agents
- Agentverse Almanac manifest API page returned HTTP 200: https://docs.agentverse.ai/api-reference/almanac/get-manifest
- Fetch Network Almanac overview returned HTTP 200: https://network.fetch.ai/docs/introduction/almanac/introduction
- Agentverse product page returned HTTP 200: https://www.fetch.ai/agentverse
- Fetch/uAgents payment source and docs are recorded in `research/PAYMENT_RAILS_RESEARCH.md`.

## Native uAgents/MCP path

Decision: recommended now.

Reason:

- It uses existing uAgents identity/addressing/dispatch/protocol rails.
- It composes with the existing `uagents_adapter.mcp.protocol` message models already used by this repo.
- It maps cleanly to Hermes `hermes mcp serve`, which is the real seam in the current Hermes checkout.
- It keeps Hermes as the local execution agent and treats uAgent sender identity as routing identity, not trust.

Proof in this repo:

- fake local dispatcher demo;
- real Hermes stdio MCP demo;
- default-deny policy and side-effecting tool denial;
- audit redaction;
- payment dry-run negotiation using official uAgents payment models.

## Agentverse mailbox path

Decision: recommended now as hosted transport, but blocked on operator account/linking.

Reason:

- Mailbox mode is the right hosted path for local machines behind NAT/firewalls.
- The repo can now start the bridge in mailbox mode when `UAGENT_SEED` is supplied by the operator shell.
- Hosted Agentverse account/linking cannot be performed by automation without secrets/account access.

Operator steps are in `research/HOSTED_DEMO_BLOCKER.md`.

## Almanac / manifest discovery

Decision: recommended now for documentation and hosted proof, not for local CI network calls.

Reason:

- Fetch/Agentverse docs expose manifest lookup/upload/model endpoints.
- uAgents protocol manifests and digests are the discovery/introspection story for remote agents.
- Local CI should not publish manifests or pay registration fees.

Current stance:

- All checked local and mailbox example configs keep `publish_manifest: false` by default.
- Hosted publication/registration should be an explicit operator opt-in only after any Agentverse/Almanac fee or funding prompt is reviewed.
- A future hosted evidence pass should record the protocol digest/manifest lookup result without secrets.

## A2A external-agent path

Decision: recommended later, not in the first upstream PR.

Source and package check:

- Agentverse A2A external-agent docs are reachable.
- The pinned local environment has `uagents_core.contrib.protocols.payment` but does not have `uagents_core.adapters` or `uagents_core.adapters.a2a.agentverse_sdk`.
- The standalone repo also does not depend on a separate `a2a` package.

Reason:

- A2A appears useful for Agentverse/ASI:One external-agent interoperability and Agent Card metadata.
- It likely requires a public endpoint and a separate adapter/package path not present in the current pins.
- Adding A2A now would expand the scope beyond the native uAgents/MCP proof and risk a larger upstream PR.

V2 scope:

- verify the current A2A package and adapter versions;
- generate an Agent Card from the same allowlisted Hermes tool policy;
- keep A2A default-off;
- add local tests that do not require Agentverse secrets;
- decide whether A2A belongs beside, not instead of, the uAgents/MCP bridge.

## Payment / agentic economy

Decision: recommended now as optional negotiation infrastructure only.

Implemented:

- config modes: `disabled`, `dry_run`, `testnet`, `real_operator_approved`;
- default mode: `disabled`;
- dry-run demo and tests using official payment message models;
- idempotent references and audit fields;
- no wallet calls, no FET movement, no secret handling.

Operator-owned:

- any testnet funding;
- any FET direct settlement;
- any Skyfire/USDC setup;
- any production spend.

## Upstream simplification

First Hermes PR should be a small optional plugin/command for the native uAgents/MCP bridge. It should not include A2A, real settlement, or gateway platform adapter work unless maintainers request that direction.
