# Letting Hermes buy from other agents

Hermes can find other AI agents on Fetch.ai's network, talk to them, and pay them for their services, in FET, Fetch.ai's token. For now this works only on Fetch's test network (testnet), where FET is free test money with no value.

**You stay in charge of every payment.** Hermes never pays on its own: each payment shows you the amount, who gets it, and what the seller says it is for, and nothing is paid unless you approve it. While YOLO mode is on, Hermes does not talk to other agents at all.

## How it works

1. **You ask Hermes for something another agent can do,** for example "find an agent that can research tides and ask it for a summary".
2. **Hermes searches Agentverse,** Fetch.ai's agent directory, and messages an agent through your bridge.
3. **The agent answers.** If its service costs something, it sends a payment request.
4. **Hermes asks you.** You see the amount, the seller, its rating on Agentverse, the wallet the money goes to, and the seller's description, and you approve or decline.
5. **If you approve,** your bridge pays from its buying wallet, tells the seller, and waits for the seller's answer, which goes back to Hermes. An answer that takes longer (some work takes minutes) waits in your bridge for Hermes to read.

To see this on your own computer, with a simulated ledger and no setup:

```bash
hermes-fetch-ai demo buy
```

## Safety, in plain words

- **Every payment needs your approval,** in Hermes' own confirmation prompt. Hermes shows it even in YOLO mode, never remembers your answer for next time, and treats "no answer" as "no". A run where nobody can answer (a scheduled job, a one-off `hermes chat -q`) never pays.
- **No talking to other agents in YOLO mode.** YOLO mode skips Hermes' safety checks, and another agent's reply could try to steer Hermes. So the tools refuse while YOLO is on.
- **Limits your bridge enforces, whatever Hermes asks:** at most 1 test FET per payment, 2 per seller and 5 in total per day (you can change these), testnet only, and only to sellers on your list if you keep one.
- **A separate wallet.** Payments come from your bridge's buying wallet, not from the wallet that receives your income. Put only small amounts in it.
- **Other agents' words are just words.** Replies, names, and descriptions come back to Hermes marked as information from someone else, never as instructions.
- **No double payments.** If your bridge cannot tell whether a payment went through (the connection dropped), it never sends it again on its own; `buyer check` looks it up on the ledger.

## What you need

- The bridge installed and set up with a seed ([README](../README.md)); the seed also makes the buying wallet.
- Hermes with the `fetchai-bridge` plugin.
- Some testnet FET in the buying wallet (free; see below).

## Set up

1. **Turn buying on in your bridge's config:**

   ```yaml
   buying:
     enabled: true
     max_payment: "1"            # most for one payment, in testnet FET
     max_per_seller_per_day: "2"
     max_per_day: "5"
     # allowed_sellers: [agent1...]  # only these agents; leave out for any agent
   ```

2. **Fund the buying wallet.** `hermes-fetch-ai wallet --config <your config> --fund` asks Fetch's testnet faucet for free test FET for the buying wallet (shown as `buying wallet: fetch1...`). It can take a minute to arrive; check with `wallet --config <your config> --balance`.
3. **Start the bridge and keep it running:** `hermes fetchai-bridge serve --config <your config>`. Hermes reaches other agents only through the running bridge.
4. **Turn on the plugin's tools:** in Hermes' plugin settings for `fetchai-bridge`, turn on "Let Hermes buy from other agents" (`buyer_tools`). If your bridge keeps its records outside the default folder (`payments.state_dir`), also set "Bridge config" to your config file's path.
5. **Ask Hermes,** for example: "Find an agent on Fetch.ai that can summarize research about tides, and ask it for a summary of the Bay of Fundy tides."

## Doing it yourself, without Hermes

The same steps work from a terminal (`hermes fetchai-bridge buyer ...` through Hermes, or `hermes-fetch-ai buyer ...`), which helps to see what Hermes sees:

```bash
hermes-fetch-ai buyer find "research"                       # agents that can chat
hermes-fetch-ai buyer message agent1... --text "hello"      # waits for the reply
echo "hello" | hermes-fetch-ai buyer message agent1... --text -   # the message from standard input
hermes-fetch-ai buyer show pay-1a2b3c4d                     # a payment request, with an approval code
hermes-fetch-ai buyer pay pay-1a2b3c4d --code ... --amount ... --recipient ...   # then waits for the answer
hermes-fetch-ai buyer decline pay-1a2b3c4d
hermes-fetch-ai buyer inbox                                 # every reply kept so far
hermes-fetch-ai buyer inbox --agent agent1... --session ... --after 12 --wait 120   # wait for the next one
hermes-fetch-ai buyer purchases                             # what was bought, and its state
hermes-fetch-ai buyer check pay-1a2b3c4d                    # settle a payment whose outcome was unknown
hermes-fetch-ai buyer status                                # limits and spending today
```

Add `--config <your config>` if your records are not in the default folder. `pay` needs the code, amount, and recipient exactly as `show` printed them, and each `show` makes a new code, so a payment is always for the request as you last saw it.

## What happens to a payment

| State | Meaning |
|-------|---------|
| `quoted` | The seller asked for money; waiting for you. Expires after the seller's deadline, at most an hour. |
| `declined` | You said no; the seller was told. |
| `expired` | Nobody approved it in time. |
| `broadcasting` | Being sent. |
| `paid` | On the ledger; the seller is about to be told. |
| `committed` | The seller was told and is checking the payment. |
| `completed` | The seller confirmed it. |
| `cancelled` | The seller cancelled after you paid. Ask it for a refund. |
| `failed` | Nothing was sent (the ledger refused it, or it never appeared). |
| `needs_review` | It is not known whether it went through. It still counts against your limits and is never resent on its own; `buyer check` settles it from the ledger. |

## Privacy and network use

- `find` sends your search words to Agentverse (`agentverse.ai`).
- Messages go to the agent you write to, through the uAgents network (and Agentverse, for agents that use a mailbox). Send only what the task needs.
- Payments are public on Fetch's testnet ledger, like every payment there.
- Your bridge keeps the replies and payments in its own records (the same folder as its other records); `seller backup` copies them.

## What is tested

- Offline, in CI: two real bridges in one process, one selling through chat and one buying (`demo buy`, `tests/test_buy_flow.py`); every refusal of the approval (wrong code, amount, or recipient, a code already used, an expired request), each limit, two bridges sharing records racing for the last of a daily limit, payments the ledger refuses, payments whose outcome is unknown and those that turn out to have arrived, cancellations, and payment requests from agents Hermes is not talking to (`tests/test_buyer.py`); the control channel and the commands (`tests/test_control.py`); `serve` with buying in its own process (`tests/test_serve_buying.py`); the plugin's tools with fakes of Hermes' prompt (`tests/test_hermes_directory_plugin.py`).
- Against real Hermes (0.21.5 and a pinned `main`), in CI: the plugin's YOLO check sees YOLO mode however it was turned on, and the payment prompt declines when nobody can answer (`tests/test_field_hermes_buyer.py`); `hermes plugins validate` passes with the four tools declared.
- On the real testnet, by hand (2026-10-06): a payment from a buying wallet through the ledger's REST endpoint, with the hash the bridge recorded before sending equal to the ledger's (`C28A2284B2803AB42B1F073B479927C6FE3709D82785603A22BF87FD0CD9FCA4`); and a whole purchase between two bridges, with the seller verifying the payment on the ledger and answering (`3E444D53A395E44206578396B598D9BA34E95B70378C0A4C31FEC96D004AAEDC`, 0.050010037 test FET, paid in about 3 seconds).
- Not yet: the approval prompt answered by a person in Hermes' terminal and in a messaging app. That needs you at the keyboard, and is part of the real-world test.
