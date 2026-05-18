# Payment Operator Actions

Status: dry-run verified; hosted/testnet/mainnet settlement not verified.

No real payment action is required for the current proof. The repository implements disabled-by-default dry-run payment negotiation. It does not move FET, call a wallet, or require funding for local validation.

Verified:

- Dry-run payment command completes.
- No value moved.
- Payment behavior remains disabled by default outside explicit dry-run/test plans.

Not verified:

- Hosted payment settlement.
- Testnet settlement.
- Mainnet settlement.
- Wallet authorization.

Next operator action:

1. Choose dry-run only (default), or explicitly approve a bounded real-value test later.
2. If approving real value, provide the exact approval sentence from [FET_TEST_FUNDS_PLAN.md](FET_TEST_FUNDS_PLAN.md).
3. Provide network, amount, config path, and recipient scope before any value movement.

Do not ask Hermes to custody secrets. Do not commit secrets. Do not run any command that spends real FET in CI or in this proof branch.
