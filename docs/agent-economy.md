# Agent economy (design, in development)

This is the design for letting Hermes take part in Fetch.ai's agent economy. Nothing here is released yet. Each section says what has landed; the rest is the plan the code is being built against.

## What it will do

- **Sell services.** The owner defines a few services (for example "research a topic"), each with a price, input limits, and a runner. Other agents call them over the bridge's MCP messages, and ASI:One users reach them in plain language through Fetch's chat protocol. Buyers pay in FET.
- **Buy services.** Hermes can find agents on Agentverse, ask them for work, and pay them. Every payment asks the owner first.
- **Testnet only.** Payments use Fetch's Dorado testnet (test FET with no value). Mainnet stays locked until a security review and the other conditions under [Before mainnet](#before-mainnet).

## Why the bridge does the verification

Fetch's Agent Payment Protocol defines the messages (`RequestPayment`, `CommitPayment`, `CompletePayment`, `CancelPayment`, `RejectPayment`) but leaves checking the payment to the seller. Fetch's own examples are labeled demo-only, and the public example seller trusts the amount the buyer claims, accepts the same transaction more than once, and converts amounts with floating point. The bridge closes each of these.

## Selling over MCP calls

1. A buyer calls a priced service. All of the bridge's normal checks run first (rate limits, policy, replay protection, argument checks).
2. Without payment, the reply is an error that starts with `payment required:` followed by JSON terms: price, recipient, network, chain id, and a reference. The reference is a signed token that carries the terms, so a flood of quote requests stores nothing.
3. The buyer sends testnet FET to the recipient with the reference as the transaction memo, then repeats the call with the reference and the transaction hash.
4. The bridge reads the transaction from the ledger itself and checks: it succeeded; it sends the right denomination to the right address; the amount is at least the price (exact integers); the memo matches the reference; it was made inside the quote's time window; the hash has never been used. The check and the record of the hash happen in one database transaction that survives restarts.
5. The service runs once. If the runner fails for an infrastructure reason, the payment stays as a credit the buyer can retry.

## Selling through chat (ASI:One)

The bridge speaks Fetch's chat protocol and answers with a menu of services and prices. A chosen service gets a `RequestPayment` in the exact shape ASI:One's testnet payment card expects. ASI:One may not put the reference in the memo, so chat quotes also carry a unique amount tag that binds the payment to the quote. Long work runs in a small bounded queue, and the bridge only asks for money when it has room to do the work.

Chat requests never reach the owner's Hermes. Each service has its own runner: a program the owner configures, or a separate guest Hermes with its own home, its own model key, and only the tools that service needs. Before every run the bridge checks that the guest's configuration still has those limits and refuses otherwise.

## Buying

- The running bridge is the buyer: it has a registered identity that can receive other agents' replies, and a separate buying key.
- Hermes reaches the bridge through three plugin tools: find agents, message an agent, and pay. They are off until the owner turns on the plugin's buyer setting.
- **Every payment asks the owner,** through the confirmation prompt Hermes uses for its own payment-card fills. That prompt ignores YOLO mode and saved approvals and declines when nobody is there to answer. The prompt shows the amount, the seller, its Agentverse rating, and the recipient, taken from the bridge's own records.
- **Hermes does not talk to other agents in YOLO mode,** because another agent's reply could otherwise trick it into running commands without asking.
- **The bridge enforces limits whatever Hermes does:** testnet only, a cap per payment, per seller, and per day, payment only of quotes it stored, and no automatic retry when a payment's outcome is unknown.

## Before mainnet

All of these must hold before mainnet can be unlocked:
- an outside security review of the payment code;
- a decision on where the agent's seed lives (today in Hermes' `.env`, which the Hermes agent could read through its terminal);
- a refund procedure;
- prices set in US dollars and converted when quoting;
- confirmation that the owner's model-provider terms allow serving third parties;
- legal review for any regulated service;
- the bridge running as its own operating-system user.

## Status

| Part | State |
|------|-------|
| Scope, threat model, and test-network guard | Landed |
| Paid services over MCP calls | Planned |
| Chat and ASI:One | Planned |
| Guest Hermes runners | Planned |
| Buying, plugin tools, approvals | Planned |
| Guided setup and plain-language docs | Planned |
| Live testnet tests and real-world trial | Planned |

The threats this design addresses are listed in [`security.md`](security.md#payments-in-development).
