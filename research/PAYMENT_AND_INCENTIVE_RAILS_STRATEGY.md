# Payment and Incentive Rails Strategy

## Bottom line

The repo currently supports payment negotiation dry-run, not real settlement.

Official Fetch/uAgents sources prove a payment protocol message model and rail-agnostic identifiers. They do not, by themselves, prove that Hermes tool calls can settle real FET/mainnet or any other real-value payment in this repo.

Therefore:

- V1 may demonstrate dry-run payment gating.
- Testnet/sandbox can be a future operator-approved experiment.
- Real-value/mainnet movement requires explicit operator approval and a separate production plan.

## Source-backed facts

Official sources:

- `raw/external-sources/uagents-core-payment.py` from `https://raw.githubusercontent.com/fetchai/uAgents/main/python/uagents-core/uagents_core/contrib/protocols/payment/__init__.py` defines:
  - `Funds(amount, currency, payment_method="fet_direct")`.
  - `RequestPayment`.
  - `RejectPayment`.
  - `CommitPayment`.
  - `CancelPayment`.
  - `CompletePayment`.
  - `payment_protocol_spec` named `AgentPaymentProtocol`, version `0.1.0`.
- `raw/external-sources/fetch-agent-payment-protocol.md` from `https://innovationlab.fetch.ai/resources/docs/agent-communication/agent-payment-protocol.md` describes `Funds.payment_method` as payment-rail agnostic and lists common values including `stripe`, `skyfire`, and `fet_direct`.
- Local implementation files `src/hermes_fetch_ai/payments.py`, `payment_policy.py`, and `payment_protocol.py` implement dry-run behavior using official model classes.
- Local tests `tests/test_payment_policy.py` and `tests/test_payment_demo.py` cover dry-run config, request/commit/complete behavior, rejection of real-shaped transaction IDs, and the demo statement that no real funds moved.

## Payment protocol map

Official source interaction graph (`raw/external-sources/uagents-core-payment.py`):

1. `RequestPayment` can be followed by `CommitPayment` or `RejectPayment`.
2. `CommitPayment` can be followed by `CompletePayment` or `CancelPayment`.
3. `CompletePayment`, `CancelPayment`, and `RejectPayment` are terminal.

Roles in official source:

- `seller`: `CommitPayment`, `RejectPayment`.
- `buyer`: `RequestPayment`, `CancelPayment`, `CompletePayment`.

Note: the cached guide text has an example section whose role wording differs from the source. Prefer official source code when there is a discrepancy, and record this as a review caveat rather than inventing semantics.

## Proof levels

### 1. Disabled payment

Default state.

- `payment.mode: disabled`.
- Tool calls are controlled by normal local policy.
- No payment messages are required.

Use for:

- Local proof.
- Most docs.
- Non-economic demonstrations.

### 2. Dry-run payment

Current supported economic proof.

- `payment.mode: dry_run`.
- Uses official uAgents-core payment models.
- Generates synthetic references/transaction IDs.
- Does not connect to a wallet, Stripe, Skyfire, chain RPC, or payment processor.
- Rejects real-shaped transaction IDs in the local dry-run store.

Use for:

- Demonstrating gating semantics.
- Testing request/commit/complete/cancel flow.
- Explaining incentive hooks without moving value.

Verification command:

`.venv\Scripts\python.exe -m hermes_fetch_ai.cli demo payment --config examples\payment-dry-run.yaml`

Expected public wording:

- "Payment dry-run demonstrates protocol-level negotiation and gating. No real funds moved."

Forbidden wording:

- "Hermes can settle FET payments."
- "This demo proves mainnet payments."
- "The bridge handles wallet custody."

### 3. Testnet/sandbox payment

Not implemented/proven in this pass.

Allowed only after:

- Operator names the rail: FET testnet, Stripe test mode, Skyfire sandbox, or other.
- Operator approves use of non-production credentials/funds in the current context.
- Secrets stay out of repo/docs.
- Transaction/session IDs are recorded only if redacted and safe.
- Failure/cancel path is tested.

Deliverable if pursued:

- A separate runbook and verification artifact under `research/**`.

### 4. Real-value/mainnet payment

Out of scope for automatic execution.

Required before any real movement:

- Explicit operator approval in the current context.
- Wallet custody decision owned by the operator.
- Review of legal/commercial obligations by the responsible human.
- Clear max amount, recipient, rail, rollback/incident process, and audit record.

This pass must not move real FET, call live payment processors for settlement, or write wallet secrets.

## Incentive model for v1

The only safe v1 incentive model is policy-level gating:

1. A caller asks for a priced tool.
2. Bridge returns a `RequestPayment` using official protocol models.
3. Caller commits with a dry-run transaction ID.
4. Bridge marks the dry-run payment complete and then permits the demo tool call.

This is useful because it proves where economics would plug in without pretending a settlement rail exists.

## Incentive model for later

A later operator-approved version may support:

- Sandbox Stripe checkout session verification.
- Skyfire sandbox/token verification.
- FET testnet transaction hash verification.
- Credit/quota accounting for known senders.

Each rail needs a separate verifier. `Funds.payment_method` is an identifier, not a verifier.

## Required guardrails

1. No secret-bearing config.
   - `src/hermes_fetch_ai/config.py` rejects secret-shaped YAML and requires seed via environment for mailbox flows.

2. No real-shaped transaction IDs in dry-run.
   - `tests/test_payment_policy.py` verifies rejection/cancel behavior.

3. No automatic mainnet branch.
   - `payment.mode: real_operator_approved` should stop the run until a human authorizes it.

4. Audit without secrets.
   - `src/hermes_fetch_ai/audit.py` and `_redaction.py` must continue avoiding raw args, raw outputs, and credential values.

5. Clear docs.
   - `docs/payment-rails.md` must distinguish dry-run, sandbox/testnet, and real-value/mainnet.

## Review caveats

- The official payment guide cache mentions Stripe/Skyfire/FET direct examples, but local code only proves dry-run negotiation.
- The official source code and guide wording should be reconciled for role labels if upstream docs/source remain inconsistent.
- No wallet custody design is proposed here; that is deliberate.
