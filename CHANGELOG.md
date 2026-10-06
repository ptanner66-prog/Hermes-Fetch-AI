# Changelog

All notable changes are documented here. The project follows [semantic versioning](https://semver.org/).

## Unreleased (after 1.0.0)

### Added

- Sell services for testnet FET ([`docs/payments.md`](docs/payments.md)). Services the owner defines appear to other agents as `service.<name>` tools. An unpaid call gets the price and payment terms; the buyer pays on Fetch's testnet with the quote as the memo and repeats the call with the transaction hash. The bridge reads the transaction from the ledger itself, binds it to a signed quote for that buyer and request, and records it so it can never be used twice, also across restarts. Off unless `payments.enabled` is set; mainnet is locked.
- `command` service runner: runs the owner's program with the request on stdin and sends back what it prints, without a shell, in an empty temporary folder, with an environment allowlist, a timeout, and an output cap. Failures on the seller's side keep the buyer's payment for a retry.
- Each service runs `max_running` requests at once with `max_waiting` more in line; when the line is full, buyers are told it is busy before they pay. A selling bridge handles each message in its own task, so a long job never holds up other requests. A buyer who missed a paid answer can collect it again with the same payment for an hour.
- Example services: a defensive code security review by an AI model on the seller's own machine, with no tools ([`examples/services/code_review.py`](examples/services/code_review.py)), and a template for your own program, with [`examples/paid-services.yaml`](examples/paid-services.yaml).
- CLI: `demo paid` (an offline sale with a simulated ledger), `wallet` (addresses and, with `--balance`, the income wallet's balance), `ledger` (checks the ledger endpoint is the testnet), and `seller credits | try | pause | resume | ban | unban | backup`. `doctor` reports payments and fails when a service program is missing; `serve` refuses to start then.
- `examples/call_bridge.py` can pay for a service on testnet with `--pay`, from the wallet of `HERMES_FETCH_PAYER_SEED`, up to `--max-fet`.
- Tested on Fetch's real testnet: a paid call, replays, a copied transaction, an underpayment of one `atestfet`, a wrong memo, and a restart ([results](docs/payments.md#tested-on-the-real-testnet)).
- Sell services to ASI:One users through Fetch's chat protocol ([`docs/asi-one.md`](docs/asi-one.md)), with `chat.enable_chat`: a plain-language menu, a payment request in the shape ASI:One's payment card reads, payments verified on the ledger, and the answer. Chat prices carry an order code (a surcharge of up to 0.000066 FET) that ties a payment without a memo to its order.
- `agentverse register` lists a selling bridge on Agentverse (README from its services, chat and payment protocols, optional `agent.handle`) with an API key from `AGENTVERSE_API_KEY`, which the Hermes plugin offers as a secret setting. `demo chat` shows a chat sale offline.

### Changed

- The project's scope now includes Fetch.ai's agent economy on testnet: selling services to other agents and ASI:One users, and paying other agents with the owner's approval. The design and its threat model are in `docs/architecture.md` (decision 9) and `docs/security.md`.
- uAgents 0.25.5 and uagents-core 0.4.9, the versions Fetch tests its examples with. uAgents now resolves testnet addresses without a network prefix.
- With `publish_manifest: true`, the bridge registers through the Almanac API only and no longer looks up the Almanac contract, so it never spends from its wallet on its own. `agent.ledger_registration: true` restores contract registration.

### Tests

- The default test run fails any test that connects outside this machine, even when the code under test hides the error. Live tests opt out with the `network` marker.
- `serve` sells a service in its own process against a ledger on 127.0.0.1, which shows the bridge makes no ledger request before a paid call arrives.

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
