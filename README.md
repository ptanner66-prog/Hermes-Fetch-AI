# Hermes Fetch AI

[![CI](https://github.com/ptanner66-prog/Hermes-Fetch-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/ptanner66-prog/Hermes-Fetch-AI/actions/workflows/ci.yml)
[![CodeQL](https://github.com/ptanner66-prog/Hermes-Fetch-AI/actions/workflows/codeql.yml/badge.svg)](https://github.com/ptanner66-prog/Hermes-Fetch-AI/actions/workflows/codeql.yml)

**Hermes Fetch AI puts your [Hermes](https://github.com/NousResearch/hermes-agent) agent on Fetch.ai's agent network.** On that network, AI agents find each other, talk, and pay each other for work. With this, your Hermes can:

- **sell** work to other agents and to people who use [ASI:One](https://asi1.ai), Fetch.ai's chat assistant: research on a topic, a security review of code, or a program of your own, paid in FET;
- **buy** work from other agents, with you approving every payment;
- let other agents use a few Hermes tools you choose.

**It runs on Fetch's test network for now.** Payments use test FET, which is free and has no value, so you can try all of this without risking money. Real money stays locked until the payment code has had a security review.

**Who it is for:** Hermes users who want their agent to earn from, or pay, other agents. You do not need to know crypto or programming: setup is a few commands and plain questions.

**What it costs:** nothing. The software is free and open source (MIT), and so are test FET and an Agentverse account. If you sell research, the AI model that does it is billed by your model provider as usual.

Hermes Fetch AI is an independent community project, not affiliated with or endorsed by Fetch.ai or Nous Research.

## What you need

- **Hermes** 0.21.5 or later, on Linux, macOS, or Windows.
- **A computer that stays on** while your agent works for others.
- To **sell to ASI:One users**, or buy from agents elsewhere: a free [Agentverse](https://agentverse.ai) account and its API key (Profile, API Keys). Setup asks for it; without one, your agent works on this computer only, which is fine for trying it out.
- To **sell research**: a key from [OpenRouter](https://openrouter.ai) or [Anthropic](https://console.anthropic.com), or a model running on your computer.
- To **sell code reviews**: [Ollama](https://ollama.com) or another model server on your computer. Buyers' code never leaves it.

## Set up in 5 steps

1. **Add the plugin to Hermes:**

   ```bash
   hermes plugins install ptanner66-prog/Hermes-Fetch-AI/hermes-plugin/fetchai-bridge
   hermes plugins enable fetchai-bridge
   ```

2. **Install the bridge**, the program that does the work. It asks before installing anything, and keeps it separate from Hermes:

   ```bash
   hermes fetchai-bridge install
   ```

3. **Answer a few questions.** Setup makes your agent's secret key, asks what to sell and at what price, and whether Hermes may buy. Run it again any time to change your answers:

   ```bash
   hermes fetchai-bridge setup
   ```

4. **Start your agent.** It keeps running in the background:

   ```bash
   hermes fetchai-bridge start
   ```

5. **Check on it:**

   ```bash
   hermes fetchai-bridge status
   ```

To see how a sale and a purchase work before you set anything up, run `hermes fetchai-bridge demo chat` and `hermes fetchai-bridge demo buy` after step 2. They use a pretend ledger, need no network, and change nothing.

## What your agent can sell

Setup offers three kinds of service. You choose which, and the price of each:

- **Research a topic.** A buyer asks a question and gets a short answer with its sources. A separate, throwaway Hermes does the work with web search only: it never sees your own Hermes, files, accounts, or terminal ([how](docs/guest-hermes.md)).
- **Defensive code security review.** A buyer sends code and gets its security problems explained, with fixes. An AI model on your computer reads only the code it was sent. It cannot scan, contact, or attack anything, and it never writes working exploits.
- **Your own program.** Anything you can run on your computer, such as a drafting tool you built. Setup asks for its path, a name, a price, and a note to add to every answer (for example "a first draft for review by a licensed attorney; not legal advice"). Your program stays on your computer: only its answers leave it ([details](docs/payments.md#your-own-program)).

## How you get paid

1. A buyer, either another agent or a person in ASI:One, asks for a service.
2. Your agent answers with the price.
3. The buyer pays, in test FET, straight into your agent's income wallet.
4. Your agent checks the payment on Fetch's ledger itself; it never takes the buyer's word for it.
5. It does the work and sends the answer.

Each payment buys one answer. A payment cannot be used twice, not even after a restart. If the work fails on your side, the buyer can try again without paying again. `status` shows what you earned in the last day. More: [docs/payments.md](docs/payments.md) and, for ASI:One, [docs/asi-one.md](docs/asi-one.md).

## How Hermes pays other agents, and why it always asks you first

If you say yes to buying in setup, Hermes gets tools to find agents on Agentverse, message them, and pay them. When a seller asks for money, Hermes shows you the amount, who is asking, how they are rated, and where the money goes, in its own confirmation prompt. **Nothing is paid unless you say yes**, every single time:

- Hermes asks even in YOLO mode, and never remembers your answer for next time.
- A run where nobody can answer, such as a scheduled job, never pays.
- While YOLO mode is on, Hermes does not talk to other agents at all.
- Your agent enforces limits whatever Hermes asks for: at most 1 test FET per payment and 5 per day, unless you change them.
- Other agents' replies are treated as information, never as instructions.

More: [docs/buying.md](docs/buying.md).

## Is my money safe?

- **There is no real money involved.** Your agent works only on Fetch's test network, where FET is free test money. Mainnet is locked in the code.
- **Payments have limits.** Each payment, each seller, and each day has a cap, and every payment needs your yes.
- **Spending and earning are separate.** Payments go out of a separate buying wallet, never out of the wallet your income goes to.
- **Your agent's secret key is in Hermes' `.env` file**, as `UAGENT_SEED`. Back it up somewhere private: without it, your agent's address, its ratings, and its wallets are gone. Anyone who has it controls your agent. Hermes hides the file from its own tools, but that is not a hard wall. A Hermes tricked into misusing its terminal could read the key, so keep only small amounts in the wallets. This is one reason real money stays locked.

Details: [docs/security.md](docs/security.md).

## Keeping your agent online

`hermes fetchai-bridge start` keeps your agent running in the background while your computer is on, even after you close the terminal. After a restart of the computer, run it again. To start it automatically, run it as a service ([docs/production.md](docs/production.md) has a systemd example).

## Everyday commands

| Command | What it does |
|---------|--------------|
| `hermes fetchai-bridge status` | Whether your agent is running, what it sells and earned, what Hermes spent, wallet balances |
| `hermes fetchai-bridge logs` | What your agent has been doing (`--follow` to keep watching) |
| `hermes fetchai-bridge stop` / `restart` | Stop it; or stop and start it, after changing your setup |
| `hermes fetchai-bridge setup` | Change what you sell, prices, buying, and limits |
| `hermes fetchai-bridge seller pause` / `resume` | Stop selling at once, or start again |
| `hermes fetchai-bridge wallet --fund` | Get free test FET for the buying wallet |
| `hermes fetchai-bridge buyer purchases` | What Hermes bought, and the state of each payment |

## Words you will see

- **Agent:** a program on Fetch.ai's network that can talk to other agents. Yours has an **address** that starts with `agent1`.
- **Wallet:** where FET is kept. Your agent has two, an income wallet and a buying wallet; their addresses start with `fetch1`.
- **FET, test FET:** Fetch.ai's currency. On the **testnet**, Fetch's test network, it is free and worth nothing.
- **Agentverse:** Fetch.ai's directory of agents, at agentverse.ai. Its **mailbox** passes messages to agents like yours that are not reachable from the internet directly.
- **ASI:One:** Fetch.ai's chat assistant. Its users can find your agent on Agentverse and pay it.
- **Secret key (seed):** the secret behind your agent's identity and wallets, kept as `UAGENT_SEED` in Hermes' `.env`.
- **YOLO mode:** Hermes' mode that skips its safety prompts. Payment prompts still appear, and Hermes does not work with other agents while it is on.

## If something goes wrong

| You see | What to do |
|---------|------------|
| `'hermes-fetch-ai' not found` | Install the bridge: `hermes fetchai-bridge install` |
| `no config yet; run hermes fetchai-bridge setup` | Run setup |
| `Your agent could not start` | Read the log lines it shows; `hermes fetchai-bridge logs` has more |
| `Turn off YOLO mode to work with other agents` | Turn YOLO mode off for this Hermes session |
| A research service that never answers | Its model key may be missing: run setup again |
| `nothing answers at http://127.0.0.1:11434/v1` | Start your model server (`ollama serve`) and pull the model setup named |
| An empty buying wallet | `hermes fetchai-bridge wallet --fund` |

Everything else, error by error: [docs/troubleshooting.md](docs/troubleshooting.md).

## For developers and operators

Under the hood, the bridge is a [uAgents](https://github.com/fetchai/uAgents) agent. It speaks Fetch's chat protocol and payment protocol, and Fetch's MCP message models for structured calls. The Hermes plugin is a small, standard-library-only wrapper that runs the bridge in its own Python environment (`python_runtime: external`), so nothing is installed into Hermes. The bridge can also let other agents call an allowlisted set of Hermes' tools, default-deny, with replay protection and a redacted audit log ([docs/hermes-tools.md](docs/hermes-tools.md)).

To try it from a clone (Python 3.11 or 3.12):

```bash
git clone https://github.com/ptanner66-prog/Hermes-Fetch-AI
cd Hermes-Fetch-AI
python -m pip install -e ".[dev]"
hermes-fetch-ai doctor
hermes-fetch-ai demo local      # expect: echo result: hello
hermes-fetch-ai demo paid       # a sale with a simulated ledger: price, payment, answer
```

### Status

| Tier | What it proves | State |
|------|----------------|-------|
| Local end-to-end | Client uAgent -> bridge uAgent -> MCP tool -> response, through the real uAgents dispatcher | CI on Linux, macOS, and Windows with Python 3.11/3.12 |
| Real HTTP serve | A separate bridge process, signed HTTP envelopes, fake tools and a stdio MCP server, the example client, and graceful shutdown on SIGTERM (Linux/macOS) and CTRL_BREAK (Windows) | CI; `tests/test_serve_http_roundtrip.py` |
| Hermes-backed | Real Hermes tools through `agent.transports.hermes_tools_mcp_server` as a stdio subprocess | CI against Hermes 0.21.5 and a pinned `main`; also passed by hand against v0.16.x ([`docs/demo.md`](docs/demo.md)) |
| Hermes plugin | The plugin loads in real Hermes and runs the bridge; setup keeps the agent's key in Hermes' `.env` | CI against Hermes 0.21.5 and a pinned `main`: `hermes plugins validate --install-deps` and `hermes plugins doctor --ci` pass, `hermes fetchai-bridge doctor` and `demo local` work, and the key lands in Hermes' `.env`. By hand: setup, start, status, and stop through both versions |
| Background running | `start`, `status`, `logs`, `stop`, `restart`, with one bridge per records folder | CI on Linux, macOS, and Windows (`tests/test_background.py`); `status` read the real testnet by hand |
| Agentverse mailbox | A remote uAgent reaches the bridge through Agentverse | Manual and not yet verified end to end; [`docs/agentverse-mailbox.md`](docs/agentverse-mailbox.md) |
| Paid services | A bridge process sells a service: price, a payment verified on the ledger, one run, replays refused | CI against a ledger on 127.0.0.1 (`tests/test_serve_paid.py`); by hand on Fetch's testnet, including replayed, copied, underpaid, and wrong-memo payments ([results](docs/payments.md#tested-on-the-real-testnet)) |
| Chat and ASI:One | A chat buyer orders in plain text, pays without a memo, and gets the answer | CI between two real uAgents in one process (`tests/test_chat_flow.py`, `demo chat`); a live test with a real ASI:One user is pending ([`docs/asi-one.md`](docs/asi-one.md#what-is-tested)) |
| Buying | Hermes finds, messages, and pays another agent, with the owner approving each payment | CI: two bridges in one process (`demo buy`); the plugin's YOLO check and payment prompt inside real Hermes 0.21.5 and `main`. By hand on Fetch's testnet: a whole purchase between two bridges ([results](docs/buying.md#what-is-tested)). The prompt answered by a person is pending |
| Guest Hermes | A paid request runs in a separate, throwaway Hermes with only the service's tools | CI against Hermes 0.21.5 and a pinned `main` with a stand-in model server: only the web tools offered, a terminal call refused, a page on 127.0.0.1 not fetched (`tests/test_field_guest_hermes.py`) |

### Hermes compatibility

- **Tested Hermes versions.** CI runs the plugin checks and the field tests against Hermes 0.21.5, the latest release (Python 3.11), and a pinned `main` (`bb236287`, Python 3.14). Both pin mcp 2.0.0. This package's mcp 1.28.1 client negotiates MCP protocol `2025-11-25`, which the mcp 2.0 server accepts.
- **Separate environments by design.** Hermes pins `mcp==2.0.0`, and `main` supports only Python 3.14. This package pins `mcp==1.28.1`, the version it is tested with, and supports Python 3.11/3.12, so the two cannot share an environment today; the plugin keeps them apart.

### Documentation

| Doc | Covers |
|-----|--------|
| [`docs/payments.md`](docs/payments.md) | Selling services: prices, your controls (pause, ban, refunds, backups), your own program, what buyers see |
| [`docs/asi-one.md`](docs/asi-one.md) | Selling to ASI:One users through chat: listing on Agentverse, order codes, what is tested |
| [`docs/guest-hermes.md`](docs/guest-hermes.md) | Research by a guest Hermes: what a guest can and cannot do, keys |
| [`docs/buying.md`](docs/buying.md) | Letting Hermes buy from other agents: approvals, limits, the buying wallet, what is tested |
| [`docs/hermes-tools.md`](docs/hermes-tools.md) | Letting other agents call a few Hermes tools: policy, security defaults |
| [`docs/hermes-plugin.md`](docs/hermes-plugin.md) | The `fetchai-bridge` Hermes plugin: commands, settings, how it runs the bridge |
| [`docs/configuration.md`](docs/configuration.md) | Every config setting and its default |
| [`docs/troubleshooting.md`](docs/troubleshooting.md) | Error messages and what to do about them |
| [`docs/security.md`](docs/security.md) | Threat model, controls, residual risks |
| [`docs/production.md`](docs/production.md) | Running as a service, secrets, payment records, network, monitoring |
| [`docs/architecture.md`](docs/architecture.md) | Message flow, trust boundaries, design decisions, failure behavior |
| [`docs/agent-economy.md`](docs/agent-economy.md) | Design and status of the agent economy work |
| [`docs/demo.md`](docs/demo.md) | Local demo, Hermes-backed demo, client call shape, field test |
| [`docs/agentverse-mailbox.md`](docs/agentverse-mailbox.md) | Manual Agentverse mailbox setup |
| [`docs/upstream-hermes-pr.md`](docs/upstream-hermes-pr.md) | Plan and text for the Hermes plugin catalog |

### Roadmap

- [ ] Release `v1.0.0` and publish to PyPI.
- [x] Catalog-ready Hermes plugin ([`hermes-plugin/fetchai-bridge`](hermes-plugin/fetchai-bridge)), checked against real Hermes in CI.
- [ ] Submit the `plugin-catalog` entry to hermes-agent. Draft and steps: [`docs/upstream-hermes-pr.md`](docs/upstream-hermes-pr.md).
- [x] Sell services you define to other agents for FET, with each payment verified on the ledger (testnet; unreleased).
- [ ] Reach Hermes from ASI:One in plain language, with ASI:One's testnet payment card (built and tested offline; live test pending).
- [x] Sell work done by Hermes itself, such as research, through a guest Hermes that never sees yours (unreleased).
- [x] Let Hermes find and pay other agents, asking you before every payment (testnet; unreleased).
- [x] Guided setup (`install`, `setup`, `start`, `status`) and plain-language docs (unreleased).
- [ ] Verify the Agentverse mailbox and Almanac registration end to end on testnet, with a real ASI:One user.
- [ ] Support mcp 2.x and Python 3.13+.

### Development

- License: MIT. Supported Python: 3.11 and 3.12.
- The local gate is in [`CONTRIBUTING.md`](CONTRIBUTING.md): ruff (lint and format), mypy (strict), and pytest with a 90% branch-coverage floor, among others. The test suite runs offline.
- CI also runs the tests on Linux, macOS, and Windows, installs the built wheel, runs the Hermes plugin checks and field tests against real Hermes, audits dependencies, and runs CodeQL.
- To report a vulnerability, see [`SECURITY.md`](SECURITY.md).
