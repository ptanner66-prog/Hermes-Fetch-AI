# Agentic Economy Product Strategy

## Positioning

Hermes Fetch AI should be positioned as a thin, policy-aware bridge that lets the Hermes runtime participate in Fetch/uAgents/Agentverse rails.

The product claim is not "Hermes becomes a marketplace." The product claim is:

- Hermes supplies local agent intelligence, MCP/tool execution, audit, redaction, and operator approvals.
- Fetch/uAgents/Agentverse/Almanac supply identity, addressing, registration, discovery, delivery, hosted surfaces, quotas, adapters, and payment negotiation primitives.

Source basis:

- Agentverse external uAgents and adapters docs: `raw/external-sources/agentverse-external-uagents.md`, `agentverse-adapters-overview.md`.
- uAgents/adapter package sources: `raw/external-sources/uagents-pyproject.toml`, `uagents-adapter-pyproject.toml`, `uagents-adapter-readme.md`.
- Local bridge implementation: `src/hermes_fetch_ai/*.py`, examples, and tests.

## Target users

1. Hermes operator/developer
   - Wants to expose a very small safe subset of Hermes capability to other agents.
   - Needs local authority boundaries and auditability.

2. Fetch/uAgents developer
   - Wants a real local runtime behind a uAgent endpoint rather than a toy handler.
   - Needs clear docs on policy and proof levels.

3. Upstream reviewer
   - Needs evidence that the bridge is thin, secure by default, and not overclaiming hosted/payment capabilities.

## V1 product surface

V1 should include only:

- Local demo proof.
- Agentverse mailbox/hosted proof runbook.
- Public docs explaining Fetch rails and proof levels.
- Dry-run payment demo using official uAgents-core payment models.
- Security model and review artifacts.

V1 should not include:

- Marketplace/search-ranking product.
- Wallet custody.
- Real FET movement.
- Real Stripe/Skyfire settlement.
- Broad public access to Hermes tools.
- Any legal-tech/private project examples.

## Value proposition

### For Hermes

- Gains a credible route to the agentic economy without building new rails.
- Can publish a public proof with policy/audit guardrails.
- Keeps operator authority local.

### For Fetch/uAgents/Agentverse

- Demonstrates a non-trivial MCP/tool runtime behind uAgents rails.
- Shows safe integration patterns for local tools.
- Uses official payment protocol models without pretending dry-run equals settlement.

### For operators

- Clear stages: local proof, hosted proof, dry-run payment, testnet/sandbox, real-value/mainnet.
- Explicit stop signs around credentials, seeds, wallets, and real funds.

## Product principles

1. Source-backed claims only.
   - Every factual rail claim should cite an official URL or local cache file.

2. Identity is not trust.
   - uAgent addresses/signatures/Agentverse registration do not bypass local policy.

3. Default-deny public surface.
   - Start with one harmless tool (`echo`) before exposing anything else.

4. No custody.
   - The bridge must not store wallet private keys or seed phrases in config/docs.

5. Operator approval for real value.
   - Any real settlement/testnet/mainnet action is an authority boundary.

6. Thin bridge over broad platform.
   - Use Fetch rails; do not recreate them.

## Roadmap

### Phase 0: Research and docs

Deliverables:

- Required research artifacts.
- Public docs.
- Source ledger/compliance matrix.
- Verification results and review status.

Success condition:

- Docs are source-backed, non-hype, and pass contamination/security self-audit.

### Phase 1: Local proof

Deliverables:

- Local demo command works.
- Policy/audit tests pass.
- README links to docs.

Success condition:

- A reviewer can run the local demo with no credentials and see a safe tool call.

### Phase 2: Agentverse mailbox proof

Deliverables:

- Operator-run proof with `UAGENT_SEED` supplied through environment.
- Agentverse account/API key and public endpoint/mailbox setup captured with secrets redacted.
- Negative proof without seed fails closed.

Success condition:

- A live Agentverse/mailbox path can reach the bridge without exposing secrets or bypassing policy.

### Phase 3: Payment dry-run proof

Deliverables:

- Dry-run payment demo proves request/commit/complete/cancel semantics using official models.
- Docs clearly state no funds moved.

Success condition:

- Payment gating can be discussed without implying settlement.

### Phase 4: Testnet/sandbox settlement experiment

Deliverables:

- Separate operator-approved plan.
- Non-production rail only.
- Captured identifiers redacted.
- Failure/cancel flow tested.

Success condition:

- A real non-production rail can be validated without mainnet risk.

### Phase 5: Mainnet/real-value consideration

Deliverables:

- Separate production plan.
- Explicit current-context operator approval.
- Wallet custody decision.
- Commercial/legal/security review.

Success condition:

- Only after operator and reviewers decide that production settlement is warranted.

## Packaging strategy

Use three layers:

1. Public docs for users/reviewers:
   - `docs/fetch-uagents-bridge.md`.
   - `docs/agentverse-hosted-proof.md`.
   - `docs/payment-rails.md`.
   - `docs/agentic-economy-thesis.md`.

2. Research docs for maintainers:
   - Master report, rails map, blueprint, payment/security/product strategies.

3. PR review package:
   - PR description, checklist, review report, review status, adversarial review.

## Success metrics

- Local demo passes from a clean checkout.
- Mailbox no-seed command fails closed.
- No secrets appear in docs/audit output.
- Public docs contain no private project references.
- Payment docs distinguish dry-run/testnet/mainnet.
- Reviewers can trace every Fetch rail claim to an official URL or local cached source.
