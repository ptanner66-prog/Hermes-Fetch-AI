# Selling services for FET

Your bridge can sell services to other AI agents on Fetch.ai's network and get paid in FET, Fetch.ai's token. For now this runs only on Fetch's test network (testnet), where FET is free test money with no value, so you can try everything without risking anything.

## How it works

1. **You decide what to sell.** Each service is a program on your computer, with a name, a description, and a price, such as "Defensive code security review, 0.1 FET".
2. **Another agent asks for a service.** Your bridge answers with the price and where to pay.
3. **The other agent pays.** It sends FET on Fetch's ledger (the public record of every payment), labels the payment with the code your bridge gave it, and asks again with its receipt.
4. **Your bridge checks the payment itself.** It looks the payment up on the ledger and never takes the buyer's word for it. If the payment is right, the service runs once and the buyer gets the answer.

Each payment pays for one request. A payment that was already used is refused, also after your bridge restarts, and so is a payment that someone copied from the public ledger. A buyer who missed the answer can ask again with the same payment within an hour and gets the same answer, without the work being done twice.

## Words used here

- **FET**: Fetch.ai's token. On testnet it is called test FET and is free.
- **Testnet (Dorado)**: Fetch's test network, `dorado-1`. Mainnet, where FET has real value, is locked in this version.
- **Wallet**: an address that holds FET, such as `fetch1...`. Your agent's wallet comes from its seed.
- **Seed** (`UAGENT_SEED`): the secret that is your agent's identity and wallet key. Anyone who has it controls your agent and its money; if you lose it, you lose both. Back it up somewhere safe and never share it.
- **Transaction hash**: the receipt number of a payment on the ledger, 64 letters and digits.

## Set up

You need the bridge installed ([README](../README.md)) and a seed in `UAGENT_SEED`. Then:

1. **Write the config.** Copy [`examples/paid-services.yaml`](../examples/paid-services.yaml) and change every `/path/to/...` to the real path on your computer (programs must be given as full paths; `which python3` prints Python's).
2. **Check it.** `hermes-fetch-ai doctor --config paid-services.yaml` checks the file and that every service program exists. It ends with `doctor: ok`.
3. **Try a service without payment.** `hermes-fetch-ai seller try word-count --request "hello there" --config paid-services.yaml` runs it once on your computer and prints the answer. Errors from the program are shown here, never to buyers.
4. **See where the money goes.** `hermes-fetch-ai wallet --config paid-services.yaml` shows your agent's address and the wallet that receives payments; add `--balance` to ask the ledger how much it holds.
5. **Start selling.** `hermes-fetch-ai serve --config paid-services.yaml`. The bridge refuses to start if a service program is missing, so it never takes payments for work it cannot do.

Receiving payments costs nothing, so your agent's wallet does not need any FET to sell.

To see a whole sale without any setup, run `hermes-fetch-ai demo paid`. It uses a simulated ledger, so it needs no network, seed, or FET.

## What you can sell

### A defensive code security review with a local AI model

[`examples/services/code_review.py`](../examples/services/code_review.py) reviews code a buyer sends and returns the security problems it finds, with fixes. The code goes to an AI model running on your own computer and nowhere else, and the model has no tools: it cannot scan, connect to, or attack anything. It is told never to write working exploits.

To run it, start a local model server with an OpenAI-compatible API. With [Ollama](https://ollama.com): install it, then `ollama pull qwen2.5-coder:7b`. The example config gives the program Ollama's address and that model with `--url` and `--model` in its `argv`; change them for another server (it must be on this computer) or model. Try it with `seller try security-review --request "<some code>"` before selling it.

The example turns off URL checks for this service (`check_urls: false`), because code often contains addresses such as `http://localhost`. That is safe here because the program never fetches anything.

### Your own program

Any program can be a service. For each paid request, the bridge:
- starts the program given in `runner.argv` (full paths, no shell), in a new empty temporary folder;
- gives it only a few environment variables (`PATH`, `LANG`, `TZ`, locale settings, and `HOME` and `TMPDIR` pointing at that folder), plus any you name in `pass_env`;
- writes `{"request": "<what the buyer asked>"}` to its standard input;
- sends what it prints back to the buyer, with the service's `disclaimer` added at the end.

Exit with status 0 when the answer is ready. Exit with any other status if something went wrong on your side, such as a model server that is down: the buyer keeps the payment and can repeat the call, up to `payments.max_attempts` times (3 by default). A program that runs longer than `timeout_seconds` is stopped, and so is one that prints more than `max_output_chars`, whose answer is cut off with a note. What the program prints to standard error never reaches the buyer.

Through Hermes (`hermes fetchai-bridge serve`), the bridge itself gets only a short list of environment variables, so a variable named in `pass_env` may not reach it. Give a program its settings as arguments in `argv` instead, as the code review does; keep secrets such as API keys in the program's own configuration, never in `argv` or the bridge's config.

[`examples/services/word_count.py`](../examples/services/word_count.py) is a small template to start from. A program you keep private never needs to be in this repository: point `argv` at it on your computer.

### Research and services run by a separate Hermes

A research service needs web search and a model, which a separate, locked-down Hermes will provide in the next version ([design](agent-economy.md)).

## Prices

Prices are in testnet FET, written as text: `price: "0.05"`. They can have up to 18 decimal places and be at most 1000. `"0"` makes a service free: it runs without payment, still with every other check and limit.

Every amount is handled as a whole number of the smallest unit (1 FET = 10^18 `atestfet`), never as a floating-point number, so an underpayment of a single unit is caught.

## Your controls

| Command | What it does |
|---------|--------------|
| `seller credits --config <file>` | Lists payments: what was paid, for which service, and its state, plus extra payments to refund. `--status failed` shows only the failed ones. |
| `seller try <service> --request "..." --config <file>` | Runs a service once on your computer, without payment. |
| `seller pause` / `seller resume` | Stops or restarts selling at once. While paused, services are hidden and calls are refused. |
| `seller ban <agent1q...> --reason "..."` / `seller unban <agent1q...>` | Stops or allows one agent. |
| `seller backup --to <new file>` | Copies the payment records, safely, even while the bridge runs. |
| `wallet --balance` | Shows how much FET the income wallet holds. |

Each service also has `max_runs_per_day` (200 by default), so strangers cannot run up unlimited work, and every buyer is held to the bridge's per-sender rate limits. A service runs `max_running` requests at once (1 by default) with up to `max_waiting` more in line (4 by default). When the line is full, new buyers are told the service is busy before they are asked to pay, and a buyer who already paid keeps the payment for a later try. While one service works, the bridge keeps answering everyone else.

### Payment states

`seller credits` shows each payment's state:

| State | Meaning |
|-------|---------|
| `paid` | Verified and waiting to run, or waiting for the buyer to retry after a failure on your side. |
| `running` | The service is running now. A bridge that stopped mid-run puts these back to `paid` when it starts. |
| `done` | The service ran and the buyer got the answer. |
| `failed` | The service failed `max_attempts` times. Refund the buyer. |
| `lapsed` | Not used within `redeem_window_seconds` of the payment (24 hours by default). Refund the buyer if they ask. |

### Refunds

There is no refund command yet; it arrives with the code that lets Hermes send payments. Until then, send the FET back from any Fetch wallet to the payer address that `seller credits` shows. Besides `failed` and `lapsed` payments, `seller credits` lists every `extra payment, refund it`: a second payment for a price that was already paid.

Payments the bridge refused (too little, the wrong label, sent after the price expired) are not in `seller credits`, because they never matched a price. A buyer who made such a mistake can send you the transaction hash, and you can look the payment up on the ledger.

## Where payment records live

The bridge keeps payment records in a small database, `payments.sqlite3`, in a folder per agent address under `payments.state_dir`. The default is `$XDG_STATE_HOME/hermes-fetch-ai` (usually `~/.local/state/hermes-fetch-ai`) on Linux and macOS, and `%LOCALAPPDATA%\HermesFetchAI` on Windows. The folder is readable only by you.

Back it up with your seed, and do not delete it: the database is what remembers which payments were already used. `hermes-fetch-ai seller backup --to <new file> --config <file>` makes a copy, even while the bridge runs. See [`production.md`](production.md#payment-records).

## Privacy and network use

A bridge that sells services contacts nothing extra until a paid call arrives. Then it reads the ledger through `payments.ledger_url` (Fetch's public endpoint by default): once per start to confirm it is the testnet, then one lookup per new payment, by transaction hash. Listing services and quoting prices stay on your computer.

## For agent developers: buying a service

A service appears in `ListTools` as the tool `service.<name>`, with one string argument, `request`, and its price in the tool's `_meta`:

```json
{
  "name": "service.word-count",
  "description": "Word count. Counts the words in your text. Price: 0.01 testnet FET per request (Fetch testnet, paid on the ledger).",
  "inputSchema": {
    "type": "object",
    "properties": {
      "request": {"type": "string", "minLength": 1, "maxLength": 4000, "description": "What you want, in plain language."}
    },
    "required": ["request"],
    "additionalProperties": false
  },
  "_meta": {
    "hermes_fetch_ai": {"price": "0.01", "currency": "FET", "denom": "atestfet", "chain_id": "dorado-1", "network": "testnet", "payment_method": "fet_direct"}
  }
}
```

1. **Call it** with replay metadata, like any tool. Without payment, the reply's `error` is `payment required: ` followed by JSON:

   ```json
   {"amount": "0.01", "amount_base": "10000000000000000", "chain_id": "dorado-1", "currency": "FET",
    "denom": "atestfet", "expires_at_ms": 1791268489953, "memo": "hfq1.…", "network": "testnet",
    "payment_method": "fet_direct", "recipient": "fetch1...", "reference": "hfq1.…", "service": "word-count", "v": 1}
   ```

   The quote is bound to your agent address and to the exact arguments, and is valid until `expires_at_ms`. Asking for a price does not use up your request ID.

2. **Pay** `amount_base` `atestfet` to `recipient` on `dorado-1`, in one plain transfer from one wallet, with `memo` as the transaction memo.

3. **Call again** from the same agent identity with the same arguments, fresh replay metadata, and the payment proof under the reserved key:

   ```json
   {"request": "hello there",
    "_hermes_fetch_ai": {"request_id": "...", "issued_at_ms": 1791268490000,
                         "payment": {"reference": "hfq1.…", "tx_hash": "518F266E…"}}}
   ```

   If the reply is `payment pending: ...`, the ledger has not shown the payment yet: wait a few seconds and repeat this call.

4. **Missed the answer?** A service can take minutes, longer than a short synchronous wait. Repeat step 3 (same identity, same arguments, same proof, fresh replay metadata) within an hour to get the answer again; the service does not run twice. The answer is kept in the seller's memory only, so it is gone after an hour or a restart.

[`examples/call_bridge.py`](../examples/call_bridge.py) does all three: set `HERMES_FETCH_PAYER_SEED` to a seed whose wallet holds testnet FET and run it with `--tool service.<name> --request "..." --pay`. It prints the paying wallet's address, pays only on testnet, and never pays more than `--max-fet` (0.1 by default). To get free testnet FET for that wallet from Fetch's faucet:

```bash
python -c "from cosmpy.aerial.client import NetworkConfig; from cosmpy.aerial.faucet import FaucetApi; FaucetApi(NetworkConfig.fetchai_stable_testnet()).get_wealth('fetch1...')"
```

### Errors a buyer can get

| Error | Meaning |
|-------|---------|
| `payment required: {...}` | The price and how to pay (above). |
| `payment pending: ...` | The payment is not on the ledger yet, the ledger did not answer, or you hit the limit on payment checks (6 per minute by default). Try again shortly. |
| `payment invalid: underpaid: ...` | The payment is less than the price. |
| `payment invalid: the transaction memo must be the quote reference` | The memo is missing or different. |
| `payment invalid: ...` | Some other part of the payment is wrong: recipient, denomination, more than a plain transfer, more than one payer, failed on the ledger, made before the quote, or arrived after it expired. |
| `payment already used` | This transaction already paid for something. |
| `this payment was already used for a completed request` | The request this payment bought already ran, and its answer is no longer kept (after an hour, or after the seller restarted). |
| `this service is busy; try again in a few minutes` | Every running and waiting place for the service is taken. No payment was asked for. |
| `this service is busy; ...; your payment is kept, so you can repeat the call shortly` | You paid, but the line filled up meanwhile. Repeat the call with the same proof later. |
| `quote does not match this call` | The reference was issued to another agent or for other arguments. Pay and call from the same identity with the same arguments. |
| `quote expired` | The quote's redeem window has passed. Ask for a new price. |
| `this quote was already paid by another transaction; ...` | You paid twice for one quote; the second payment is recorded so the seller can refund it. |
| `<problem>; your payment is kept, so you can repeat the call with the same reference` | The service failed on the seller's side. Repeat the call with the same proof. |
| `this request failed too many times; ask the seller for a refund` | The service failed `max_attempts` times. |
| `this service has reached its limit for today; try again tomorrow` | The service's daily limit (`max_runs_per_day`). |
| `this agent is not taking requests right now` | The seller paused selling. |

## Tested on the real testnet

On 2026-10-06 a bridge running `serve` sold the `word-count` service on Fetch's testnet (`dorado-1`), checking payments against Fetch's public ledger endpoint. A separate buyer, funded from the faucet, paid with `examples/call_bridge.py --pay` and got the answer within six seconds of starting. Then each of these was refused:

| Attempt | Answer |
|---------|--------|
| The used transaction with a new quote, same and different request | `payment already used` |
| Another agent presenting the buyer's reference and transaction | `quote does not match this call` |
| Another agent with its own quote and the buyer's transaction | `payment already used` |
| A real payment 1 `atestfet` short of the price | `payment invalid: underpaid: 0.049999999999999999 FET of 0.05 FET` |
| A real payment of the full price with the wrong memo | `payment invalid: the transaction memo must be the quote reference` |
| The used transaction again after a restart | `payment already used` |

After the change that keeps paid answers for an hour, a third paid call worked the same way; the buyer repeating it with the same payment got the same answer without the service running again, and another agent presenting that payment got `quote does not match this call`.

The paying transactions were `518F266EA453BC09275D8AD40A224E8FB55358E6376858BEBB4BD7F557FA36C4`, `CB458BF7CC9F1E782E67A1EF0018EC1AFE74DA014BECCF12D4B11EC719B7F320`, and `1A3478D40D70D520441C832DBF0EEE03C8010860F49C84457A2E8AEAB31E2733`; the audit log and logs held only shortened hashes and addresses.

## Limits of this version

- Testnet only. Mainnet stays locked until the conditions in [`agent-economy.md`](agent-economy.md#before-mainnet) are met.
- Refunds are manual.
- Buyers reach services through MCP calls only; plain-language requests from ASI:One come next.
- Hermes cannot buy from other agents yet.
