`fet-example`'s seller checks FET payments on the ledger, which is right. Four details let a buyer underpay or reuse a payment, and turn away some honest payments. This fixes them without changing the payment flow, the messages, or the metadata ASI:One's payment card reads.

## What happens today (`fet-example/payment.py` at `ae840c2`)

1. **The buyer sets the price.** The transfer is compared with the amount in the buyer's own `CommitPayment` (`expected_amount_fet=str(msg.funds.amount)`, line 214), not with the price the agent asked for. A buyer who commits `"0"` gets the service for a transfer of 1 atestfet.
2. **One payment pays for any number of requests.** Accepted transactions are never recorded, so the same `transaction_id` can be committed again and again.
3. **Floats round the price.** `int(float(expected_amount_fet) * 10**18)` (line 62) turns `"1.1"` into 1100000000000000128 afet, so an exact payment of 1.1 FET is refused.
4. **Only the last transfer counts.** `query_tx()` returns cosmpy's summary, which keeps one entry per event type, so with two transfers in one transaction the check sees only the last.

## The change

- **`fet-example/verify.py` (new, about 50 lines):**
  - `fet_to_base` converts FET to afet with `Decimal`.
  - `normalize_tx_hash` puts a hash in the form the ledger uses.
  - `paid_to` adds up the transaction's `MsgSend` messages from the buyer's wallet to the seller's, in the right denomination.
- **`fet-example/payment.py`:**
  - Checks against `FIXED_FET_AMOUNT`, the price the agent sent in `RequestPayment`.
  - Reads the whole transaction with `ledger.txs.GetTx`, which `query_tx` calls internally.
  - Records each verified transaction hash in `ctx.storage` before delivering, and refuses a hash it has already accepted.

No new dependencies. The reference is still not compared with the transaction's memo, because what ASI:One writes there is not documented.

## Testing

A stand-in ledger built from cosmpy's own types (no network) drives `handle_commit_payment` before and after the change:

| Case | Before | After |
|------|--------|-------|
| Pays the price | pass | pass |
| The same transaction again is refused | **fail** | pass |
| Refused: a buyer who claims 0 and pays 1 atestfet | **fail** | pass |
| Refused: an underpayment of 1 atestfet | pass | pass |
| Refused: the wrong denomination | pass | pass |
| Refused: someone else's transfer | pass | pass |
| Two transfers that add up count | **fail** | pass |
| Exactly 1.1 FET counts | **fail** | pass |

The script is [`check_payment.py`](https://github.com/ptanner66-prog/Hermes-Fetch-AI/blob/main/upstream/fetch-examples/fet-example-payment-checks/check_payment.py). Run it as `python check_payment.py fet-example`. I can add it to the example if you'd like.

## Context

I found these while building [Hermes Fetch AI](https://github.com/ptanner66-prog/Hermes-Fetch-AI), which puts Hermes Agent on Fetch.ai's network as a seller and a buyer, using the Agent Chat Protocol and the Agent Payment Protocol. It checks payments the same way, and also ties each chat payment to its order. Happy to adjust this to the repo's conventions.
