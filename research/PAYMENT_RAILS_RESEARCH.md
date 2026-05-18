# Payment Rails Research

Status: source-backed for the package versions pinned by this repo.

## Package pins

`pyproject.toml` pins:

- `uagents==0.24.2`
- `uagents-core==0.4.4`
- `uagents-adapter[mcp]==0.6.2`

## Source access

Source access succeeded with `gh`, GitHub raw URLs, and local wheel inspection. No fallback-only claim is used here.

Primary source links:

- Fetch docs: https://uagents.fetch.ai/docs/guides/agent-payment-protocol
- Payment protocol source, exact core tag: https://github.com/fetchai/uAgents/blob/core%400.4.4/python/uagents-core/uagents_core/contrib/protocols/payment/__init__.py
- Same payment file under uAgents v0.24.2 tag: https://github.com/fetchai/uAgents/blob/v0.24.2/python/uagents-core/uagents_core/contrib/protocols/payment/__init__.py
- uAgents protocol role behavior: https://github.com/fetchai/uAgents/blob/v0.24.2/python/src/uagents/protocol.py

## Official API

The current official import path is:

```python
from uagents_core.contrib.protocols.payment import (
    Funds,
    RequestPayment,
    RejectPayment,
    CommitPayment,
    CancelPayment,
    CompletePayment,
    payment_protocol_spec,
)
```

Model fields in `uagents-core==0.4.4`:

- `Funds(amount: str, currency: str, payment_method: str = "fet_direct")`
- `RequestPayment(accepted_funds: list[Funds], recipient: str, deadline_seconds: int, reference: str | None, description: str | None, metadata: dict | None)`
- `RejectPayment(reason: str | None)`
- `CommitPayment(funds: Funds, recipient: str, transaction_id: str, reference: str | None, description: str | None, metadata: dict | None)`
- `CancelPayment(transaction_id: str | None, reason: str | None)`
- `CompletePayment(transaction_id: str | None)`

`payment_protocol_spec` is named `AgentPaymentProtocol`, version `0.1.0`. The source interactions are:

- `RequestPayment -> CommitPayment | RejectPayment`
- `CommitPayment -> CompletePayment | CancelPayment`
- terminal messages: `CompletePayment`, `CancelPayment`, `RejectPayment`

Roles in source:

- `seller`: handlers for `CommitPayment`, `RejectPayment`
- `buyer`: handlers for `RequestPayment`, `CancelPayment`, `CompletePayment`

The docs examples align with that source behavior. A docs code block appears to invert role sets; for this pinned repo, the package source is authoritative.

## Payment methods and currencies

The protocol models treat method and currency as strings. Verified examples and source comments include:

- `fet_direct`, with `FET`
- `skyfire`, with `USDC`

There is no enum-level validation in `uagents-core==0.4.4`, and no settlement adapter in the payment protocol module.

## What is and is not provided

Provided by Fetch/uAgents in this module:

- standard payment negotiation message models;
- protocol specification and role wiring;
- a way for agents to request, commit, complete, cancel, or reject a payment negotiation.

Not provided by this module:

- FET transfer;
- USDC transfer;
- Skyfire API calls;
- wallet custody;
- transaction signing;
- settlement verification;
- funding or account creation.

Therefore this proof implements only optional dry-run/testnet-first negotiation rails. It does not move funds.

## What can be tested locally

Safe local tests can:

- import official payment symbols;
- instantiate and serialize the official models;
- verify protocol name/version/roles;
- exchange dry-run `RequestPayment`, `CommitPayment`, and `CompletePayment` messages using fake `dryrun-*` transaction ids;
- verify policy composition: payment never overrides tool denial.

No wallet, account, FET, USDC, Skyfire key, or hosted Agentverse setup is needed for those tests.

## What requires operator action

Any real settlement proof requires the operator to provide account/wallet/funding setup outside this repo and explicitly approve the step. FET direct settlement would require funded wallet/ledger logic outside `uagents_core.contrib.protocols.payment`. Skyfire/USDC settlement would require Skyfire/account/API rails outside the protocol module.

This run did not handle wallet secrets, did not print seeds, and did not move FET.
