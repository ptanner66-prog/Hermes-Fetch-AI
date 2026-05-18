# Payment Rails

Hermes Fetch AI currently supports a CLI dry-run payment protocol-model proof, not hosted remote payment negotiation or real settlement.

The purpose of the payment proof is to show where payment gating fits in the agent protocol without moving funds, negotiating hosted payment with a remote sender, or taking custody of wallets.

## Official payment protocol basis

The Fetch/uAgents Agent Payment Protocol defines message models such as:

- `Funds`
- `RequestPayment`
- `RejectPayment`
- `CommitPayment`
- `CancelPayment`
- `CompletePayment`

Official sources:

- Agent Payment Protocol guide: https://uagents.fetch.ai/docs/guides/agent-payment-protocol
- uAgents source repository: https://github.com/fetchai/uAgents

The protocol is rail-agnostic through `Funds.payment_method`. Documentation examples include rail identifiers such as `stripe`, `skyfire`, and `fet_direct`.

A rail identifier is not a settlement verifier. Each real rail needs separate verification.

## Proof levels

### Disabled

Default mode. Tool calls are controlled only by local policy.

### Dry-run

Current supported proof mode.

Dry-run payment:

- uses official payment protocol model classes;
- creates synthetic references and transaction IDs;
- demonstrates request/commit/complete/cancel semantics;
- does not connect to wallets, chains, Stripe, Skyfire, or payment processors;
- does not move real funds.

Run:

```bash
python -m hermes_fetch_ai.cli demo payment --config examples/payment-dry-run.yaml
```

### Testnet or sandbox

Future operator-approved proof mode.

This may use a non-production wallet, FET testnet, Stripe test mode, Skyfire sandbox, or another explicit sandbox rail. It requires a separate runbook and operator approval.

### Real-value or mainnet

Out of automatic scope.

Required before any real movement:

- explicit operator approval in the current context;
- named rail and max amount;
- wallet custody decision owned by the operator;
- legal/commercial/security review where applicable;
- rollback/cancel/incident plan;
- secret handling plan.

## Non-goals

Hermes Fetch AI v1 does not:

- custody wallet signing material;
- move real FET;
- verify real Stripe/Skyfire/FET settlement;
- build an exchange;
- launch a marketplace;
- let public callers pay to bypass Hermes policy.

Payment can add a condition to local policy. It does not replace local policy.
