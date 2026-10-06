# Selling to ASI:One users

[ASI:One](https://asi1.ai) is Fetch.ai's chat assistant. Its users can talk to agents listed on Agentverse, Fetch.ai's agent directory. Your bridge can be one of them: an ASI:One user asks for one of your services in plain language, approves a testnet FET payment in ASI:One's payment card, and gets the answer from your agent. It is all on Fetch's test network, where FET is free test money.

This builds on [selling services](payments.md); set those up first.

## What a buyer sees

1. They write to your agent, for example `@hermes-reviews what can you do?`. Any message that does not order something gets your menu: each service, what it does, and its price.
2. They order by starting with the service name: `security-review: <their code>`.
3. Your agent answers with the price, and ASI:One shows a payment card for the amount, such as 0.10002345 FET. The last digits are this order's code (see [Order codes](#order-codes)).
4. They approve, and ASI:One pays from their testnet wallet and tells your agent.
5. Your agent checks the payment on the ledger itself, confirms it, runs the service, and sends the answer.

To see this conversation on your own computer, with a simulated ledger and no setup:

```bash
hermes-fetch-ai demo chat
```

## What you need

- Everything from [selling services](payments.md): `UAGENT_SEED`, and at least one service that works with `seller try`.
- An Agentverse account (free, at [agentverse.ai](https://agentverse.ai)) and an API key with write access, from your Agentverse profile's API keys page.
- To try it as a buyer yourself: an ASI:One account with a wallet that holds testnet FET on Dorado. Fetch's examples say to turn on Developer mode (My account, Labs) and connect such a wallet under Manage payments.

## Set up

1. **Write the config.** Copy [`examples/asi-one.yaml`](../examples/asi-one.yaml), set the program paths, and pick a `handle`: lowercase letters, digits, `-` and `_`, 3 to 20 characters. Check it with `hermes-fetch-ai doctor --config asi-one.yaml`.
2. **Give the bridge your Agentverse key.** `export AGENTVERSE_API_KEY=...`, or through Hermes, set the plugin's "Agentverse API key" setting, which Hermes keeps in its `.env`. Never put the key in the config file.
3. **List your agent.** `hermes-fetch-ai agentverse register --config asi-one.yaml` (or `hermes fetchai-bridge agentverse register ...`). It asks before it lists anything; add `--yes` to skip the question. It sends Agentverse your agent's name, description, handle, the protocols it speaks, and a README written from your services and prices, which is what ASI:One reads to decide when to send users to you. Run it again after you change services or prices.
4. **Start your agent and keep it running.** `hermes-fetch-ai serve --config asi-one.yaml`. ASI:One can only reach a running agent, and Agentverse ranks active agents first. [`production.md`](production.md) shows how to keep it running.
5. **Say hello.** In ASI:One, write `@your-handle what can you do?`, or use the agent's address (`agent1q...`, printed by `hermes-fetch-ai wallet --config asi-one.yaml`).

### Mailbox mode

The example uses `agent.mode: mailbox`: Agentverse keeps messages for your agent in a mailbox, and your bridge collects them, so your computer needs no public address or open port. Messages between ASI:One and your agent pass through Agentverse.

With a public `https://` address instead, set `agent.mode: endpoint` and `agent.endpoint`; `agentverse register` then lists that address.

## Order codes

ASI:One's wallet is not known to label a payment with the reference your agent gives it, and the ASI:One payments seen on the test network had no label. Without a label, a payment could be mixed up with another one for the same price. So your agent adds a small random amount to every chat price: between 1 and 65,535 billionths of a FET, at most 0.000066 FET. The exact amount then ties each payment to one order, and someone else's payment can never pay for yours. Wallets that round amounts slightly are still matched.

When a payment does carry the reference (a label), your agent uses that instead.

## When a payment takes a while

A payment takes a few seconds to appear on the ledger. Your agent waits up to about 50 seconds. If the payment is still not there, it tells the buyer so, and the buyer sends `check` a minute later. Nothing is lost while waiting.

## If your agent restarts

Orders waiting for payment are kept in memory. If your agent restarts between the order and the payment, the payment is still accepted, and your agent asks the buyer to send the request again; it then runs without another payment. Payments themselves are always recorded on disk.

The same goes for `seller pause`: a payment that arrives after you paused is accepted and kept, and the buyer is asked to send the request again after you resume.

## Privacy

- Registration is public, and Agentverse keeps it: your agent's name, description, handle, README, and protocols.
- In mailbox mode, messages between ASI:One users and your agent pass through Agentverse.
- Your Agentverse API key is used by `agentverse register` and, if set, sent with `buyer find` searches; `serve` never sends it anywhere.
- Your agent registers its address and protocols with Fetch's Almanac through Agentverse's API, which is free. It never pays the Almanac contract on the ledger unless you set `agent.ledger_registration: true`.

## What is tested

- Offline, in CI: the whole conversation above between two real uAgents agents in one process, with the payment request in the shape of Fetch's own ASI:One payment example (`fet_direct` FET funds, the agent's wallet as recipient, `provider_agent_wallet`, and `fet_network: stable-testnet`), payments without a reference, someone else's payment, payments that are slow to appear, a declined payment, a restart, and a busy service.
- Not yet: a real ASI:One user paying a real listing. That needs your Agentverse and ASI:One logins, and its results will be recorded here. Until then, three things are unconfirmed: whether ASI:One sends the reference back with the payment, how it rounds amounts, and whether its payment card needs anything more.

## Problems

| Message | What to do |
|---------|------------|
| `agentverse: FAIL: set AGENTVERSE_API_KEY ...` | Set the key in the environment (or the plugin's setting). |
| `agentverse: FAIL: HTTP 401 ...` | The key is wrong, expired, or lacks write access. Create a new one. |
| `agentverse: FAIL: Agentverse needs to reach the agent ...` | Use `agent.mode: mailbox`, or set a public `agent.endpoint`. |
| `agentverse: FAIL: confirm with --yes when not at a terminal` | Add `--yes` when running it from a script or through Hermes' agent. |
| ASI:One does not find your agent | Check that `serve` is running. Write to the agent's address instead of the handle. A new listing can take a while to appear in search. |
| The buyer is told `I can't see your payment on the ledger yet` | Testnet can be slow. The buyer sends `check` a minute later. `hermes-fetch-ai ledger --config ...` checks that the ledger answers. |
