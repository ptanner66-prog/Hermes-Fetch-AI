# Fetch GitHub Sweep

Updated: 2026-05-17T03:35:34Z

Scope: public Fetch.ai GitHub repositories relevant to a thin Hermes <-> Fetch/uAgents bridge. This sweep used public GitHub API/raw source reads only. No account secrets or hosted Agentverse credentials were used.

## Repositories checked

Public GitHub API observations:

| Repository | Default branch | Observed head | Why it matters |
| --- | --- | --- | --- |
| `fetchai/uAgents` | `main` | `6d7008971eaf` | uAgent identity, Agent class, mailbox, dispatcher, protocol adapter package. |
| `fetchai/api-clients` | `main` | `1849f33cb1eb` | Agentverse/Almanac client surfaces including manifest lookup. |
| `fetchai/agentverse-skills` | `main` | `9b842c42c85b` | Skill packaging/context for Agentverse-facing developer experience; not needed for PR one. |
| `fetchai/cosmpy` | `main` | `c2b23eb80078` | Wallet/Cosmos dependency and observed Windows child import issue source. |
| `fetchai/fetchd` | `master` | `644eddd72a92` | Fetch network node/ledger context; out of scope for bridge PR one. |
| `fetchai/asi-alliance-wallet` | `main` | `620419d05268` | Wallet/operator settlement context; out of scope for automated proof. |
| `fetchai/agentverse` | `main` | `d79896b4eb0e` | Public Agentverse repository; hosted proof still requires operator account actions. |

## Source files checked

- `fetchai/uAgents/python/src/uagents/agent.py`
- `fetchai/uAgents/python/src/uagents/mailbox.py`
- `fetchai/uAgents/python/uagents-adapter/src/uagents_adapter/mcp/protocol.py`
- `fetchai/uAgents/python/uagents-adapter/src/uagents_adapter/mcp/README.md`
- `fetchai/uAgents/python/uagents-adapter/src/uagents_adapter/a2a_inbound/README.md`
- `fetchai/api-clients/agentverse-client/agentverse_client/almanac/aio/api/manifests_api.py`
- `fetchai/api-clients/agentverse-client/agentverse_client/almanac/aio/api/almanac_v2_api.py`
- `fetchai/cosmpy/cosmpy/__init__.py`
- `fetchai/fetchd/README.md`
- `fetchai/asi-alliance-wallet/README.md`

## Findings

### uAgents supplies identity, routing, mailbox, protocol inclusion, and network context

`uAgents` source shows the `Agent` implementation already carries the concepts this repo should not rebuild:

- wallet/network context;
- mailbox mode and Agentverse mailbox client;
- endpoint and registration/Almanac concepts;
- `Protocol` inclusion and protocol digest mapping;
- local dispatcher path used by this repo's tests/demos.

Bridge implication: this repo should keep using `uagents.Agent`, `Protocol`, signed message handlers, and dispatcher/mailbox modes. It should not create a second identity, discovery, or transport layer.

### uAgents adapter already defines the MCP protocol messages used here

`uagents_adapter.mcp.protocol` defines:

- `ListTools`
- `ListToolsResponse`
- `CallTool`
- `CallToolResponse`
- `mcp_protocol_spec`
- interactions `{ListTools: {ListToolsResponse}, CallTool: {CallToolResponse}}`
- server role `{ListTools, CallTool}`

Bridge implication: the correct first connection path is MCP-over-uAgents using the official message models/spec. This repo should own policy and validation around those messages, not invent new wire models.

### Upstream MCP adapter README points to discovery/marketplace shape but is broader than PR one

The uAgents MCP adapter README describes a bridge between MCP servers and uAgents, marketplace discovery, tool discovery/execution, and chat support.

Bridge implication: use the adapter protocol shape and manifest idea, but keep chat out of this v1 proof. This repo intentionally does not publish the adapter chat protocol or treat adapter defaults as the security boundary.

### A2A inbound adapter exists but should remain v2 for this effort

The A2A inbound README describes bridging Agentverse uAgents to the A2A ecosystem, secure communication through mailbox infrastructure, and HTTP REST endpoints compatible with A2A clients.

Bridge implication: A2A is real and relevant for later Agentverse/ASI interoperability, but it broadens the first PR. It likely needs a public endpoint and Agent Card flow. PR one should not mix A2A with the native uAgents/MCP proof unless maintainers request it.

### Agentverse/Almanac API clients expose manifest lookup surfaces

`api-clients` includes:

- `ManifestsApi.get_manifest(protocol_digest)`
- `AlmanacV2Api.get_manifest_by_name_v2(...)`
- handle availability/generation endpoints

Bridge implication: discovery and protocol manifest lookup belong to Fetch/Agentverse/Almanac rails. This repo should document how hosted proof records protocol digest/manifest evidence, while local CI keeps publication off.

### cosmpy explains the Windows child-process import hardening

`cosmpy/__init__.py` imports `google.protobuf.descriptor`. The previous run observed a Windows multiprocessing child startup failure when a copied `cosmpy/protos` path shadowed the real protobuf package.

Bridge implication: the current `uagent_app.py` hardening that removes `cosmpy/protos` from the child `sys.path` during spawn is not cosmetic; it addresses a source-backed import collision.

### fetchd and ASI Alliance Wallet are context, not bridge implementation targets

`fetchd` is the network/node implementation. `asi-alliance-wallet` is wallet/operator tooling context.

Bridge implication: this proof must not attempt ledger/node operation or wallet custody. Payment support belongs first as default-off negotiation and testnet/operator follow-up, not automatic settlement.

## PR one implications

Recommended first upstream-facing shape:

- native uAgents/MCP bridge;
- default-off;
- optional dependency;
- one small CLI or plugin command;
- same policy path for endpoint/mailbox mode;
- manifest publication off by default;
- payment dry-run only if included, with no settlement code path;
- A2A and hosted mailbox screenshots/transcripts left to a follow-up/operator proof.

## Gaps after sweep

Not agent-solvable in this run:

- Hosted Agentverse mailbox link and remote transcript.
- Almanac manifest publication proof with an operator-owned account.
- Testnet settlement proof.

Agent-solvable and now covered:

- Source-backed Fetch repo sweep.
- Native MCP protocol mapping.
- Local dispatcher proof.
- Hermes stdio proof.
- Payment dry-run proof.
- Mailbox missing-seed blocker validation.
