# Production Deployment

## Process model

One bridge per process. `serve` owns an event loop, starts the MCP backend (a stdio subprocess for real Hermes tools), runs the uAgent HTTP server, and on SIGINT or SIGTERM (CTRL_BREAK on Windows) shuts down and exits 0, closing the MCP child's stdin. `tests/test_serve_http_roundtrip.py` runs this in a separate process, in fake mode and in stdio mode, and sends SIGTERM (CTRL_BREAK on Windows).

`serve` exits with status 1 and a one-line reason when it cannot start, so `Restart=on-failure` below retries it:

- `hermes backend: FAIL: ...` when Hermes' tools server cannot start. The child's stderr is discarded because it is outside the bridge's redaction boundary; the message names the command to run by hand to see the error.
- `serve: FAIL: ...` when the HTTP server cannot start, for example because `agent.port` is taken.

If the backend dies after startup, callers get `backend unavailable` and the audit log records `decision: error`; restart the service to recover.

## Secrets

- `UAGENT_SEED` comes from the environment only. Config files with seed or mailbox-key values are rejected, mailbox mode refuses to start without the seed, and logs and audit records redact seed-shaped strings.
- The seed must be at least 32 characters, because the agent's signing key is derived from it. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"`.
- Production configs set `agent.dev_random_seed: false` (as `examples/hermes-stdio.yaml` does). With `true`, `UAGENT_SEED` is ignored and the bridge gets a new address on every start; `doctor` and `serve` print `seed: WARN` in that case.
- Use a dedicated agent seed, not a wallet that holds real funds. The seed also derives the agent's `fetch1...` wallet, which Almanac registration (`publish_manifest: true`) can spend from.
- Keep seeds, mailbox keys, API tokens, private endpoints, and connection strings out of configs, audit logs, issues, pull requests, and screenshots.
- With buying on, `serve` writes `control.json` (the control channel's port and token, mode 0600) to `payments.state_dir`, and removes it on shutdown. Treat it like a key: anyone who can read it can ask the bridge to pay, within its limits. Keep only small amounts in the buying wallet.
- A guest Hermes ([`guest-hermes.md`](guest-hermes.md)) reads its model key from its own keys file (`doctor` names it), mode 0600. Give each guest a key of its own with a spending limit at the provider, so a busy service cannot spend beyond it and the key can be cancelled alone.

## Replay-protection contract

`CallTool` requires this metadata by default, under the reserved argument key `_hermes_fetch_ai`:

```json
{
  "_hermes_fetch_ai": {
    "request_id": "unique-client-request-id",
    "issued_at_ms": 1780000000000
  }
}
```

Clients generate a fresh request ID (8 to 128 characters from `A-Z a-z 0-9 _ . : -`) for every call. The bridge strips the metadata before schema validation and before calling Hermes. A stale or future timestamp, malformed metadata, and oversized calls are denied before the tool runs. The bridge remembers a sender's request ID once the call has passed every check and is handed to the tool, so reusing it gets `replay detected`, even if the tool failed; a call denied earlier does not use up its ID. `hermes_fetch_ai.direct_protocol.replay_args()` builds the metadata for Python clients, as [`examples/call_bridge.py`](../examples/call_bridge.py) shows. The settings are in [`configuration.md`](configuration.md#policy).

## systemd unit (example)

```ini
[Unit]
Description=Hermes Fetch AI bridge
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
User=hermes-bridge
# /etc/hermes-fetch-ai/env holds UAGENT_SEED=... (owner root, mode 0600).
EnvironmentFile=/etc/hermes-fetch-ai/env
Environment=HERMES_HOME=/var/lib/hermes-fetch-ai/hermes
ExecStart=/opt/hermes-fetch-ai/venv/bin/hermes-fetch-ai serve --config /etc/hermes-fetch-ai/bridge.yaml
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/var/lib/hermes-fetch-ai

[Install]
WantedBy=multi-user.target
```

systemd only treats whole lines starting with `#` as comments, so keep comments off the `EnvironmentFile=` line. In `bridge.yaml`, set `hermes_mcp.command` to the Hermes environment's Python (a supervised `serve` does not get the Hermes plugin's interpreter hand-over) and point `logging.audit_path` at `/var/lib/hermes-fetch-ai/audit.jsonl`. The audit writer rotates the file itself at 25 MB, keeping `audit.jsonl.1` to `audit.jsonl.5`; if you also use logrotate, use `copytruncate`.

## Payment records

A bridge that sells services ([`payments.md`](payments.md)) keeps its payment records in `payments.sqlite3`, in a folder per agent address under `payments.state_dir` (for the unit above, set `state_dir: /var/lib/hermes-fetch-ai`). The bridge makes that folder readable only by its user.

- **Back it up with the seed.** The database remembers which payments were already used. Losing it lets a buyer present a payment again until its quote's redeem window closes (by default up to 24 hours after the quote expires), and loses the list of payments to refund.
- **Copy it safely.** `hermes-fetch-ai seller backup --to <new file> --config <file>` writes a consistent copy, readable only by you, even while the bridge runs. Copying the file directly can miss recent payments, which SQLite keeps in a separate write-ahead log for a while.
- **One database per agent.** Two bridges with the same seed and state folder share the database safely (SQLite serializes them), but different seeds always get different folders.
- **Versions.** The database records its schema version, and a bridge refuses a database written by a newer version rather than misreading it.

Watch `seller credits` for `failed` payments and extra payments, which need refunds.

## Network

- The bridge listens on all interfaces (`0.0.0.0`) on `agent.port`; uAgents has no bind-address setting. Firewall the port so only the callers you expect can reach it.
- With `publish_manifest: false`, the bridge makes no outbound calls of its own: no Almanac registration, contract lookup, or status reports (`tests/test_uagent_direct_protocol.py` checks this). Replying to a remote agent can need egress to Agentverse's Almanac API or the Fetch ledger, to look up that agent's endpoint.
- Mailbox mode and `publish_manifest: true` need egress to Agentverse and the configured Fetch network (Almanac REST and gRPC, mailbox HTTPS).
- Selling services needs egress to `payments.ledger_url` (`https://rest-dorado.fetch.ai` by default), only when a paid call arrives.
- Selling through ASI:One in mailbox mode needs egress to Agentverse (`agentverse.ai`): the mailbox, the Almanac API, and manifests. `agentverse register` also calls Agentverse's API with your API key.
- Buying needs egress to `payments.ledger_url` (to send payments and check them), to Agentverse (`agentverse.ai`) for `buyer find`, to the agents Hermes writes to (or Agentverse, for mailbox agents), and, for `wallet --fund`, to Fetch's testnet faucet.
- A guest Hermes needs egress to its model provider and, with the `web` toolset, to the web search services Hermes uses and the public pages it reads. Behind a proxy, list `HTTPS_PROXY` (and `HTTP_PROXY`, `NO_PROXY`) in the runner's `pass_env`; note that with a proxy, Hermes no longer resolves host names itself before refusing private addresses.

## Who can reach the bridge

- With `publish_manifest: false`, the bridge is not registered in the Almanac, so remote agents cannot discover it; only clients configured with its endpoint can call it. It still listens on `0.0.0.0:<port>`, so any host that can reach the port can call its public tools.
- Public discovery needs either `publish_manifest: true` with a reachable `agent.endpoint` (registration may need a funded wallet) or mailbox mode ([`agentverse-mailbox.md`](agentverse-mailbox.md)). Neither path is covered by CI yet; prove it on testnet first.

## Going to mainnet (checklist)

1. Prove the deployment on `network: testnet` first.
2. Set `agent.network` explicitly, and use a separate seed for mainnet.
3. Fund the derived `fetch1...` address only with what Almanac registration needs.
4. Keep `policy.public_tools` empty or minimal; the denylist wins.
5. Check that `hermes_mcp.command` points at the Hermes environment's Python and that `HERMES_HOME` is set for the service user.
6. Make sure callers attach replay-protection metadata and treat a replay denial as final.
7. Run the local gate and the field test ([`demo.md`](demo.md)) before promoting a new config.

## Monitoring

The JSONL audit log is the operational signal: decisions, reasons, durations, sizes, truncation, send status, and shortened sender addresses. Alert on:

- sustained spikes in `denied`;
- spikes in `replay detected` or stale/future replay metadata;
- `backend unavailable` errors;
- `send_status: failure`;
- repeated `args exceed max_args_bytes`, URL, or shell-character rejections;
- when selling: records with `payment: invalid` or `payment: mismatch` (someone probing the payment checks), `payment: pending` that never clears (the ledger endpoint is down), `decision: error` from a service (its program is failing), and frequent `this service is busy` refusals (raise `max_running` or `max_waiting` if the machine can take more).

`hermes-fetch-ai doctor --config /etc/hermes-fetch-ai/bridge.yaml` checks the config and the dependency pins; it does not contact a running bridge. For health, watch the process and the audit log.

## Upgrades

Dependencies are pinned on purpose. Bump them in a dedicated change, with CI green and the field test re-run ([`demo.md`](demo.md)). `doctor` reads the tested pins from the installed package's metadata and warns if the running environment has drifted from them. The dependency-audit exceptions (`PyNaCl==1.6.0` and `ecdsa`) are tracked in [`security.md`](security.md#residual-risks).
