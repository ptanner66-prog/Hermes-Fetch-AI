# Full Connection Fetch Website Addendum

Operator note, 2026-05-16:
Do not overfit the integration to one Agentverse API page. The full connection needs to line up with Fetch.ai's broader product and network story: agents that can be discovered, communicate, transact, and be routed through Agentverse / ASI / Almanac.

## Official Fetch source anchors

- Fetch.ai homepage:
  https://www.fetch.ai/
  - Fetch positions the developer path as ASI:One, Agentverse, uAgents, examples, and Network docs.
  - The homepage points developers to Agentverse for publishing agents on the decentralized marketplace and improving discoverability, uAgents for protocols and agent-to-agent communication, and Network docs for ledger, Almanac, CosmPy, and wallet infrastructure.

- Fetch.ai concepts:
  https://fetch.ai/docs/concepts
  - Fetch describes agents as the "doers" in a decentralized digital economy.
  - uAgents is the open communication layer.
  - Agentverse is the portal / hosting / discovery layer.
  - The Almanac lets agents be found and supports protocol manifest discovery.
  - FET and the Fetch ledger are part of agent payments and economic interaction.

- Agentverse product page:
  https://www.fetch.ai/agentverse
  - Agentverse is about discoverability, reach, testing, debugging, optimization, and becoming part of an open AI ecosystem.
  - The Hermes bridge must therefore expose enough metadata and manifest quality to be discoverable, not merely reachable.

- ASI / Fetch Network docs:
  https://network.fetch.ai/docs
  - The ASI Network frames Almanac, FNS, ledger, CosmPy, and wallet as the infrastructure layer.
  - The Hermes bridge must understand which parts are required for v1 and which remain optional or operator-owned.

- Almanac overview:
  https://network.fetch.ai/docs/introduction/almanac/introduction
  - The Almanac is the registered-agent directory for remote communication and discovery.
  - Protocol manifests and digests are part of how users and agents discover capabilities.

- Almanac registration:
  https://network.fetch.ai/docs/introduction/almanac/register-in-almanac
  - Registration requires an agent address and a registration fee.
  - Running an agent can trigger Almanac registration in the uAgents runtime.
  - Any real fee/payment step must be operator-approved and must not be performed by automation without explicit approval.

- Agent payment protocol:
  https://uagents.fetch.ai/docs/guides/agent-payment-protocol
  - The official workflow is role-driven: seller requests payment, buyer commits or rejects, seller completes or cancels.
  - Examples show `RequestPayment`, `CommitPayment`, `CompletePayment`, accepted funds, references, deadlines, and manifest publication.

- Agentverse Almanac API:
  https://docs.agentverse.ai/api-reference/almanac/get-manifest
  https://docs.agentverse.ai/api-reference/almanac/get-manifest-by-name
  https://docs.agentverse.ai/api-reference/almanac/upload-manifest
  https://docs.agentverse.ai/api-reference/almanac/get-protocol-model
  - These APIs provide manifest lookup/upload/model lookup surfaces that must be considered in a full connection.

## New hard gates for "FULL CONNECTION"

The project is not full connection unless it covers all of this:

1. Native uAgent message path:
   Hermes tool calls move over Fetch/uAgents protocol messages, not a bespoke transport.

2. Discoverability:
   The bridge publishes or verifies protocol manifests, captures model digests, and documents how another agent or Agentverse user discovers Hermes capabilities by address, name, digest, or manifest.

3. Agentverse and ASI fit:
   The docs explain how Hermes appears in Agentverse/ASI discovery, what metadata matters, and which quality/ranking fields are operator-owned.

4. Almanac lifecycle:
   The bridge documents endpoint/mailbox/proxy registration, re-registration/liveness expectations, and fee/FET implications.

5. Agentic economy:
   Payment rails are implemented as safe, optional, default-off protocol infrastructure. Dry-run/testnet negotiation must be tested before any real FET or external payment method.

6. Operator boundary:
   Any Fetch account, Agentverse linking, wallet, seed, fee, FET, or hosted deploy step must be listed in `research/HOSTED_DEMO_BLOCKER.md` or `research/PAYMENT_OPERATOR_ACTIONS.md`. The automation must stop and notify before real spend or secret handling.

7. Upstream simplicity:
   The Hermes PR should be a small native bridge/plugin/command that makes Hermes a uAgent participant in Fetch's existing economy. It must not import the whole standalone repo or invent a parallel marketplace.

## Required output updates

Before final acceptance, Hermes must update or create:

- `research/FETCH_FULL_CONNECTION_MAP.md`
- `research/PAYMENT_RAILS_RESEARCH.md`
- `research/UPSTREAM_PR_EXECUTION_PLAN.md`
- `research/FINAL_BOSS_STATUS.md`
- README/docs sections that describe the broader Fetch.ai/Agentverse/Network fit without marketing fluff or unsupported claims.

If the current run misses this addendum, the babysitter must relaunch a repair pass that explicitly consumes this file.
