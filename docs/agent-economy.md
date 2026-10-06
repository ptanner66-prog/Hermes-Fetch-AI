# Agent economy (design and status)

This is the design for letting Hermes take part in Fetch.ai's agent economy. Selling over MCP calls and through chat, services run by a guest Hermes, buying from other agents, and a guided setup have landed (unreleased; how to use them: the [README](../README.md), [`payments.md`](payments.md), [`asi-one.md`](asi-one.md), [`guest-hermes.md`](guest-hermes.md), [`buying.md`](buying.md)). The rest is the plan the code is being built against; the [status table](#status) says what has landed.

## What it will do

- **Sell services.** The owner defines a few services (for example "research a topic"), each with a price, input limits, and a runner. Other agents call them over the bridge's MCP messages, and ASI:One users reach them in plain language through Fetch's chat protocol. Buyers pay in FET.
- **Buy services.** Hermes can find agents on Agentverse, ask them for work, and pay them. Every payment asks the owner first.
- **Testnet only.** Payments use Fetch's Dorado testnet (test FET with no value). Mainnet stays locked until a security review and the other conditions under [Before mainnet](#before-mainnet).

## Why the bridge does the verification

Fetch's Agent Payment Protocol defines the messages (`RequestPayment`, `CommitPayment`, `CompletePayment`, `CancelPayment`, `RejectPayment`) but leaves checking the payment to the seller. Fetch's own examples are labeled demo-only, and the public example seller trusts the amount the buyer claims, accepts the same transaction more than once, and converts amounts with floating point. The bridge closes each of these.

## Selling over MCP calls (landed)

1. A buyer calls a priced service. All of the bridge's normal checks run first (rate limits, policy, replay protection, argument checks).
2. Without payment, the reply is an error that starts with `payment required:` followed by JSON terms: price, recipient, network, chain id, and a reference. The reference is a signed token that carries the terms, so a flood of quote requests stores nothing.
3. The buyer sends testnet FET to the recipient with the reference as the transaction memo, then repeats the call with the reference and the transaction hash.
4. The bridge reads the transaction from the ledger itself and checks: it succeeded; it sends the right denomination to the right address; the amount is at least the price (exact integers); the memo matches the reference; it was made inside the quote's time window; the hash has never been used. The check and the record of the hash happen in one database transaction that survives restarts.
5. The service runs once. If the runner fails for an infrastructure reason, the payment stays as a credit the buyer can retry. A buyer who missed the answer gets it again by repeating the call with the same proof, for an hour. Each service has a small line (`max_running`, `max_waiting`); when it is full, the bridge says so before asking for money.

Services run through a `command` runner: the owner's program gets the request on stdin and its output is the answer ([`payments.md`](payments.md#your-own-program)). The "bug bounty with a local AI" service is built this way: [`hermes_fetch_ai.local_review`](../src/hermes_fetch_ai/local_review.py), which ships with the bridge, sends the buyer's code only to a model server on the seller's machine and gives the model no tools. This was planned for a guest Hermes runner; a plain program is smaller and depends on no Hermes internals, so the guest runner is now for services that need Hermes' tools, such as research.

## Selling through chat (ASI:One) (landed)

The bridge speaks Fetch's Agent Chat Protocol and answers with a menu of services and prices. A chosen service gets a `RequestPayment` in the shape of Fetch's own ASI:One payment example. ASI:One may not put the reference in the memo, so chat quotes also carry an order code, a unique amount surcharge that binds the payment to the quote. Long work runs in a small bounded queue, and the bridge only asks for money when it has room to do the work. A live test with a real ASI:One user is still to come ([`asi-one.md`](asi-one.md#what-is-tested)).

Chat requests never reach the owner's Hermes. Each service has its own runner: a program the owner configures, or a guest Hermes (below).

## Services run by a guest Hermes (landed)

A research service needs Hermes itself: a model and web search. For each request the bridge starts a separate Hermes in a new, throwaway home folder, writes its settings there (the model, only the service's toolsets, every other toolset switched off by name, no memory or self-review, no private network addresses, no installs), gives it only the guest's own keys file and a short environment, and deletes the folder when the run ends. The settings are written fresh for every run, so they cannot drift; at startup the bridge also refuses any `.env` that Hermes would load into guests if it sets `HERMES_...` variables. Details and tests: [`guest-hermes.md`](guest-hermes.md).

## Buying (landed)

How to use it: [`buying.md`](buying.md).

- The running bridge is the buyer: it is the agent other agents answer, and it pays from a separate buying wallet (key index 1). Hermes' tools and the `buyer` commands reach it through a local control channel.
- Hermes reaches the bridge through four plugin tools: find agents (Agentverse search), message an agent (the Agent Chat Protocol), read its later replies, and pay (the Agent Payment Protocol's buyer role). They are off until the owner turns on the plugin's `buyer_tools` setting.
- **Every payment asks the owner,** through Hermes' own confirmation prompt (the one it uses when an MCP server asks the user to confirm something). Hermes shows it even in YOLO mode, never remembers the answer, and declines when nobody can answer. The prompt shows the amount, the seller, its Agentverse rating, and the recipient, taken from the bridge's own records.
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
| Paid services over MCP calls | Landed; tested on the real testnet |
| Chat and ASI:One | Landed; offline tests; live ASI:One test pending |
| Guest Hermes runners | Landed; field-tested against real Hermes in CI |
| Buying, plugin tools, approvals | Landed; a purchase between two bridges tested on the real testnet; the prompt answered by a person pending |
| Guided setup (`install`, `setup`, `start`, `status`) and plain-language docs | Landed; run by hand through Hermes 0.21.5 and `main`; a newcomer following the README pending |
| Live testnet tests and canaries | Landed: opt-in tests and a manual workflow; all passed on the real testnet on 2026-10-06 |
| Checked against Hermes' and Fetch.ai's documentation | Done on 2026-10-06; what it found and fixed, and what is left for the trial, is in [`validation.md`](validation.md) |
| Real-world trial (ASI:One, the Agentverse mailbox, the prompt answered by a person) | Planned, with the owner |

The threats this design addresses, and the controls that have landed, are in [`security.md`](security.md#payments).
