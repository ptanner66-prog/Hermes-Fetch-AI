# FET_TEST_FUNDS_PLAN

Current recommendation: continue with dry-run only until explicit operator approval for any real-value flow.

Default state:

- `payment.mode: dry_run`
- no non-testnet settlement
- no mainnet transaction
- no automated wallet custody

## Path 1: Dry-Run

Allowed now.

Use:

```powershell
.\.venv\Scripts\python.exe -m hermes_fetch_ai.cli demo payment --config examples\payment-dry-run.yaml
```

Purpose: verify protocol, policy, audit, and bridge behavior without settlement risk.

## Path 2: Testnet Or Sandbox

Use only if the operator can provide a safe network/account configuration that does not expose secrets.

Preconditions:

- Hosted mailbox proof is complete.
- Tool exposure remains restricted.
- Network, account, and amount are bounded.
- Logs remain redacted.

## Path 3: Mainnet Or Real FET

Do not proceed until explicit written approval.

Preconditions:

- Hosted mailbox proof is complete.
- No unexpected tool calls are exposed.
- Session logs are redacted.
- Operator confirms network, funding policy, maximum amount, recipient category/address, and stop conditions.

Required approval sentence before any real transfer or settlement:

```text
I authorize one real-FET payment test on [NETWORK], amount [X FET], to recipient [CATEGORY/ADDRESS], using config [PATH], and accept any on-chain settlement fees. Do not proceed with any other amount or recipient than stated.
```

No automated movement or deployment can happen without that explicit approval text.
