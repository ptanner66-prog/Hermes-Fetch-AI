# Changelog

All notable changes are documented here. The project follows [semantic versioning](https://semver.org/).

## Unreleased (after 1.0.0)

### Added

- Sell services for testnet FET ([`docs/payments.md`](docs/payments.md)). Services the owner defines appear to other agents as `service.<name>` tools. An unpaid call gets the price and payment terms; the buyer pays on Fetch's testnet with the quote as the memo and repeats the call with the transaction hash. The bridge reads the transaction from the ledger itself, binds it to a signed quote for that buyer and request, and records it so it can never be used twice, also across restarts. Off unless `payments.enabled` is set; mainnet is locked.
- `command` service runner: runs the owner's program with the request on stdin and sends back what it prints, without a shell, in an empty temporary folder, with an environment allowlist, a timeout, and an output cap. Failures on the seller's side keep the buyer's payment for a retry.
- Each service runs `max_running` requests at once with `max_waiting` more in line; when the line is full, buyers are told it is busy before they pay. A selling bridge handles each message in its own task, so a long job never holds up other requests. A buyer who missed a paid answer can collect it again with the same payment for an hour.
- Example services: a defensive code security review by an AI model on the seller's own machine, with no tools ([`hermes_fetch_ai.local_review`](src/hermes_fetch_ai/local_review.py), shipped with the bridge so the setup wizard can offer it), and a template for your own program, with [`examples/paid-services.yaml`](examples/paid-services.yaml).
- CLI: `demo paid` (an offline sale with a simulated ledger), `wallet` (addresses and, with `--balance`, the income wallet's balance), `ledger` (checks the ledger endpoint is the testnet), and `seller credits | try | pause | resume | ban | unban | backup`. `doctor` reports payments and fails when a service program is missing; `serve` refuses to start then.
- `examples/call_bridge.py` can pay for a service on testnet with `--pay`, from the wallet of `HERMES_FETCH_PAYER_SEED`, up to `--max-fet`.
- Tested on Fetch's real testnet: a paid call, replays, a copied transaction, an underpayment of one `atestfet`, a wrong memo, and a restart ([results](docs/payments.md#tested-on-the-real-testnet)).
- Sell services to ASI:One users through Fetch's Agent Chat Protocol and Agent Payment Protocol ([`docs/asi-one.md`](docs/asi-one.md)), with `chat.enable_chat`: a plain-language menu, a payment request in the shape ASI:One's payment card reads, payments verified on the ledger, a note as soon as a payment is confirmed (ASI:One waits about a minute for a reply), and the answer. Chat prices carry an order code (a surcharge of up to 0.000066 FET) that ties a payment to its order when it carries no reference, or one the bridge did not issue.
- `agentverse register` lists a selling bridge on Agentverse (README from the services it sells through chat, ending with a line on where the agent comes from (Hermes Agent, through Hermes Fetch AI) and the Fetch.ai protocols it speaks, each service's optional `example` as a starter prompt, exactly the protocols it speaks, and an optional `agent.handle` of lowercase letters, digits, and `-`, the characters Agentverse keeps) with an API key from `AGENTVERSE_API_KEY`, which the Hermes plugin offers as a secret setting. `demo chat` shows a chat sale offline.
- `hermes` service runner, a guest Hermes ([`docs/guest-hermes.md`](docs/guest-hermes.md)): each request runs a separate Hermes in a throwaway home folder, with only the `web` toolset (or none), settings the bridge writes (every other toolset off by name, no memory or self-review, no private network addresses, no installs), and its own keys file. The folder is deleted after the run. `doctor`, `seller try`, and `serve` refuse to run a guest when a `.env` Hermes would load into it sets `HERMES_...` variables, or `..._BASE_URL` variables, which would move its requests elsewhere (Hermes puts `CUSTOM_BASE_URL` before the address the bridge writes). The example config gains a `research` service built on it.
- Buying from other agents ([`docs/buying.md`](docs/buying.md)), off unless `buying.enabled` is set: `serve` pays other agents for their services in testnet FET from a separate buying wallet (key index 1), only for a payment request the owner approved (the amount, the recipient, and a one-time code), within per-payment, per-seller, and daily limits, never resending a payment whose outcome is unknown (including one the bridge was stopped in the middle of sending). Replies and payment requests count only from agents Hermes is talking to.
- `hermes-fetch-ai buyer find | message | inbox | show | pay | decline | check | purchases | status`, through a local control channel (127.0.0.1, a token in a 0600 file); `message` and `pay` wait for the other agent's answer, and `inbox --wait` waits for the next reply. `wallet --fund` gets free test FET for the buying wallet; `demo buy` shows a purchase offline.
- Hermes plugin: tools `fetchai_find_agents`, `fetchai_message_agent`, `fetchai_read_replies`, and `fetchai_pay`, unavailable until the new `buyer_tools` setting is on; they refuse while YOLO mode is on, and in Hermes' separate plugin host (`plugins.isolation: host`), which can neither see a session's `/yolo` nor show the prompt. `fetchai_pay` pays only after the user accepts in Hermes' confirmation prompt, then returns the seller's answer once the seller ends the conversation. The tools never raise; after an approved payment, any failure says the payment may or may not have been made and to run `buyer check`. Messages reach the bridge through standard input, not the command line. A `buy` skill, and a `config` setting.
- Tested on Fetch's real testnet: a purchase between two bridges, with the seller verifying the payment on the ledger ([results](docs/buying.md#what-is-tested)).
- Setup without editing files ([README](README.md)): `hermes fetchai-bridge install` installs the bridge version that matches the plugin, in an environment of its own, after asking. `hermes fetchai-bridge setup` makes the agent's secret key and keeps it in Hermes' `.env`, offers to keep an Agentverse API key the same way, asks in plain words what to sell (research, the defensive code review, your own programs, each with a price; research, which uses your own model account, at most 20 requests a day unless you choose otherwise) and whether Hermes may buy, checks every answer, and writes the config; running it again changes the answers. It offers free test FET and the Agentverse listing, and turns on the plugin's `buyer_tools` setting if you say so. `hermes-fetch-ai setup --answers <file>` answers from JSON.
- `start`, `stop`, `restart`, `status`, and `logs` ([`docs/production.md`](docs/production.md#running-in-the-background)): the agent runs in the background with a private log; `status` says in plain words whether it runs, what it sells, earned, and spent, the wallets' balances, and whether the testnet is making blocks.
- The plugin hands the bridge its version, and the bridge says when the two differ and how to match them.
- An agent that only buys can be listed on Agentverse, so other agents' replies reach its mailbox.
- Research can run on ASI:One's own AI model (Fetch.ai's `asi1` models, through ASI:One's OpenAI-compatible API): setup offers it, with its key kept in the guest's keys file and named by the runner's new `key_env` setting, which Hermes sends only to that address. A field test runs real Hermes against a stand-in as strict as ASI:One's API.
- [`upstream/`](upstream/README.md): ready-to-post contributions to the two projects this one builds on: the Hermes catalog entry, a feature request for a public "ask the user to confirm" plugin API, a tested fix for the payment checks in Fetch.ai's FET payment example (it trusted the buyer's stated amount, accepted a payment twice, and rounded through floats), and a note for Fetch.ai's developers with the questions only they can answer about ASI:One's payment card. A test keeps the proposed fix's checks correct.
- [`docs/validation.md`](docs/validation.md): the plugin and the bridge checked against Hermes' and Fetch.ai's documentation, what that changed, and what only the real-world trial can settle. The README shows a Hermes deny rule that keeps Hermes' terminal from running the bridge's `buyer pay`, even in YOLO mode.

### Changed

- The project's scope now includes Fetch.ai's agent economy on testnet: selling services to other agents and ASI:One users, and paying other agents with the owner's approval. The design and its threat model are in `docs/architecture.md` (decision 9) and `docs/security.md`.
- uAgents 0.25.5 and uagents-core 0.4.9, the versions Fetch tests its examples with. uAgents now resolves testnet addresses without a network prefix.
- With `publish_manifest: true`, the bridge registers through the Almanac API only and no longer looks up the Almanac contract, so it never spends from its wallet on its own. `agent.ledger_registration: true` restores contract registration.
- Commands given no `--config` use the one `setup` wrote (`~/.config/hermes-fetch-ai/bridge.yaml`, or `%APPDATA%\HermesFetchAI\bridge.yaml` on Windows); without one they say to run setup. `doctor` checks it when it exists, else the demo config as before.
- Only one bridge runs per records folder (`payments.state_dir`); a second one refuses to start.
- `agent.description` is capped at 300 characters, the limit uagents-core sets for an agent's short description on Agentverse.
- The plugin's one-line description says what it does now: sell work to other AI agents and buy from them on Fetch.ai's testnet, approving every payment.
- The README names Hermes Agent and Fetch.ai as their makers do, shows how the two halves fit together and which of each platform's parts the project uses, and ends with acknowledgments; the guides call Fetch's protocols by their names, the Agent Chat Protocol and the Agent Payment Protocol.
- The README is written for people who are not technical; the technical detail is in `docs/`, including letting other agents use Hermes' tools ([`docs/hermes-tools.md`](docs/hermes-tools.md)).

### Tests

- The default test run fails any test that connects outside this machine, even when the code under test hides the error. Live tests opt out with the `network` marker.
- `serve` sells a service in its own process against a ledger on 127.0.0.1, which shows the bridge makes no ledger request before a paid call arrives.
- A field test loads the plugin inside real Hermes and checks the buying guards: YOLO mode is seen however it was turned on, and the payment prompt declines when nobody can answer. Two bridges buy and sell in one process through uAgents' dispatcher.
- A field test runs the guest Hermes runner against real Hermes (0.21.5 and a pinned `main`) with a stand-in model server on 127.0.0.1: only the web tools are offered, a terminal call is refused, a page on 127.0.0.1 is not fetched, and nothing is left behind.
- Opt-in live tests on Fetch's Dorado testnet (`HERMES_FETCH_LIVE_TESTNET=1`, `tests/test_live_testnet.py`), run by hand or by the manual "Live testnet" workflow: the ledger reader, a payment the bridge sends, a paid call to a running bridge (with a stranger, an underpayment, a wrong memo, and a replay after a restart refused), a purchase between two bridges through chat, and Agentverse search. Test FET comes from Fetch's faucet.
- Canaries pin Fetch's chat, payment, and MCP protocol digests and the message fields ASI:One's payment card reads, and check that the Agentverse listing names exactly the protocols the agent speaks. The Hermes field test now also calls Hermes' confirmation prompt directly, so a broken prompt cannot pass as a declined one.
- `start`, `status`, `logs`, and `stop` run a real background bridge on Linux, macOS, and Windows. A field test checks, in real Hermes, that the key setup makes lands in Hermes' `.env`, readable only by the owner. Tests never touch the developer's own config or records.

## 1.0.0 - Unreleased

The first release. To release, set the date here and push the `v1.0.0` tag.

### Bridge

- A uAgents bridge that serves Fetch's MCP message models (`ListTools`, `CallTool`) over signed uAgents envelopes and runs the calls against Hermes' tools MCP server, or against two built-in fake tools for demos and tests.
- Backends: Hermes' tools server as a stdio subprocess (the production shape, tested against Hermes 0.21.5 and `main`); an in-process mode for hermes-agent v0.16.x; fake tools.
- CLI: `doctor` (version, config, dependency pins), `probe-hermes`, `demo local` (a two-agent round trip with no network), `demo mailbox`, and `serve`.
- `serve` exits with status 1 and a clear message when Hermes' tools server or the HTTP server cannot start, and shuts down cleanly on Ctrl-C or SIGTERM.
- Example configs for a local demo, Hermes over stdio, the in-process mode, and an Agentverse mailbox, plus a client, `examples/call_bridge.py`, that calls a running bridge.

### Security

- Default deny: a tool is callable only if it is public or allowlisted for the sender, and the denylist always wins. The Hermes example configs make only `skills_list` public.
- Replay protection for `CallTool`: a per-sender request ID and an issue time, checked for freshness, with a bounded in-memory cache.
- Rate limits per sender and globally, for both `ListTools` and `CallTool`.
- Argument checks: each tool's JSON schema, shell metacharacters and control characters, and URLs anywhere in the arguments, including encoded IPv4 forms and DNS answers that point at private or local addresses.
- Size caps on arguments, tool lists, and results; tool names restricted to plain ASCII.
- A JSONL audit log with an allowlist of fields (no arguments or outputs) and redaction.
- Seeds come only from `UAGENT_SEED` and must be at least 32 characters; config files that contain credential-shaped values are rejected.
- With `publish_manifest: false`, the bridge makes no outbound calls of its own: it skips the Almanac contract lookup and the status reports that uAgents otherwise makes for every agent.
- Hermes' tools server runs without a shell, with an environment allowlist and its stderr discarded.
- Dependencies pinned to tested versions, including `mcp` 1.28.1 (PYSEC-2026-3483); builds use `setuptools>=83` (PYSEC-2026-3447).

### Hermes plugin

- `hermes-plugin/fetchai-bridge`, a directory plugin for Hermes 0.21.5 or later. It is stdlib-only (`python_runtime: external`), adds `hermes fetchai-bridge`, which runs the separately installed bridge with an environment allowlist and hands it Hermes' interpreter, and ships an `operate` skill.
- A draft entry for Hermes' plugin catalog (`upstream/hermes-pr/plugin-catalog/fetchai-bridge.yaml`) and submission notes.

### Quality

- CI on Linux, macOS, and Windows with Python 3.11 and 3.12: ruff lint and format, `mypy --strict`, and the test suite, including a real HTTP round trip through `serve`.
- At least 90% branch coverage, counting the CLI and `serve` subprocesses.
- A CI job against Hermes 0.21.5 and a pinned `main`: Hermes' own plugin validator and doctor, the plugin's CLI, and a field test against Hermes' real tools server.
- Dependency audit, CodeQL, Dependabot, wheel and sdist checks, and a release workflow that can publish to PyPI through trusted publishing.

### Known limitations

- The Agentverse mailbox mode has not been verified end to end.
- `serve` listens on all network interfaces; firewall the port.
- The replay cache is in memory, and URL checks cannot stop DNS rebinding or redirects. See [`docs/security.md`](docs/security.md#residual-risks).
- The dependency audit ignores two transitive vulnerabilities with no fix that uAgents can use yet (`CVE-2025-69277` in PyNaCl and `PYSEC-2026-1325` in ecdsa); the reasons are in `docs/security.md`.
