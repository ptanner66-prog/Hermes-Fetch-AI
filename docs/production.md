# Production Deployment

## Process model

One bridge per process. `serve` owns a dedicated event loop, starts the MCP backend (stdio subprocess preferred), runs the uAgent server, and shuts down gracefully on SIGINT/SIGTERM/SIGBREAK (exit code 0; the MCP child receives a clean EOF). The two-process HTTP round trip, signed message exchange, and graceful shutdown path are covered by `tests/test_serve_http_roundtrip.py`.

If the Hermes backend cannot start, `serve` prints `hermes backend: FAIL: ...` and exits with status 1 (covered by `tests/test_cli.py`), so `Restart=on-failure` below retries it. The child's stderr is discarded because it is outside the bridge's redaction boundary; the message names the command to run by hand to see the underlying error. If the backend dies after startup, callers get `backend unavailable` and the audit log records `decision: error`; restart the service to recover.

## Secrets

- `UAGENT_SEED` comes from the environment only. The config loader rejects production YAML seed values; mailbox/hosted mode fails closed without the seed; logs and audit redact seed-shaped strings.
- The seed must be at least 32 characters because the agent's signing key is derived from it. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"`.
- Production configs must set `agent.dev_random_seed: false` (as `examples/hermes-stdio.yaml` does). With `true`, `UAGENT_SEED` is ignored and the bridge gets a new address on every start; `doctor` and `serve` print `seed: WARN` in that case.
- Use a dedicated agent seed. Fund the derived `fetch1...` wallet with only what Almanac registration needs.
- Do not put seeds, mailbox keys, API tokens, private endpoints, or connection strings in examples, audit logs, issues, PRs, or screenshots.

## Replay/idempotency contract

`CallTool` requires bridge metadata by default under reserved args key `_hermes_fetch_ai`:

```json
{
  "_hermes_fetch_ai": {
    "request_id": "unique-client-request-id",
    "issued_at_ms": 1780000000000
  }
}
```

Clients should generate a fresh request ID per attempted tool call. The bridge strips this metadata before schema validation and before invoking Hermes. Duplicate request IDs for the same sender, stale timestamps, future timestamps beyond configured skew, malformed metadata, and oversized calls are denied before tool invocation.

Relevant policy knobs:

```yaml
policy:
  require_replay_metadata: true
  replay_ttl_seconds: 300
  max_replay_entries: 8192
  max_replay_clock_skew_seconds: 60
```

## systemd unit (example)

```ini
[Unit]
Description=Hermes Fetch AI bridge
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
User=hermes-bridge
EnvironmentFile=/etc/hermes-fetch-ai/env      # UAGENT_SEED=... (mode 0600)
ExecStart=/opt/hermes-fetch-ai/venv/bin/hermes-fetch-ai serve --config /etc/hermes-fetch-ai/bridge.yaml
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/var/lib/hermes-fetch-ai

[Install]
WantedBy=multi-user.target
```

Point `logging.audit_path` at `/var/lib/hermes-fetch-ai/audit.jsonl`. The writer appends line-delimited JSON and rotates the file itself at 25 MB, keeping five rotated files (`audit.jsonl.1` to `audit.jsonl.5`). External logrotate is optional; if you use it, use `copytruncate`.

## Network egress

- Local/endpoint mode with `publish_manifest: false`: no mandatory egress for local tests. uAgents may probe the configured network at startup; failures are logged and non-fatal in local mode.
- Hosted mode (mailbox/manifest): allow egress to Agentverse and the configured Fetch network (Almanac REST/gRPC, mailbox HTTPS).

## Who can reach the bridge

- With `publish_manifest: false` the bridge is not registered in the Almanac, so remote agents cannot discover its address. Only clients that are configured with its endpoint directly can reach it, which is what `tests/test_serve_http_roundtrip.py` does.
- Public discovery needs either `publish_manifest: true` with a reachable `agent.endpoint` (Almanac registration may need a funded wallet) or mailbox mode ([`agentverse-mailbox.md`](agentverse-mailbox.md)). Neither path is covered by CI yet; prove it on testnet first.

## Going to mainnet (checklist)

1. Prove the deployment on `network: testnet` first.
2. Set `agent.network` explicitly; never reuse a testnet seed casually.
3. Fund the derived `fetch1...` address only for Almanac registration needs.
4. Keep `policy.public_tools` empty or minimal (`skills_list` at most for Hermes-backed demos); denylist wins.
5. Confirm `hermes_mcp.command` points at the Hermes environment's Python (a supervised `hermes-fetch-ai serve` does not get the Hermes plugin's interpreter hand-over) and that `HERMES_HOME` is set for the service user.
6. Confirm callers attach replay metadata and treat replay denials as final, not retriable with the same request ID.
7. Run the full local gate and the gated field test before promoting a new config.

## Monitoring

The audit JSONL is the operational signal: decisions, reasons, durations, sizes, truncation, send status, and redacted sender fingerprints. Alert on:

- sustained `denied` spikes;
- `reason: replay detected` spikes;
- stale/future replay metadata spikes;
- `send_status: failure`;
- repeated `args exceed max_args_bytes` or URL/shell validation failures.

`hermes-fetch-ai --version` and `hermes-fetch-ai doctor` are safe health probes. With the Hermes plugin enabled, `hermes fetchai-bridge doctor` runs the same check.

## GitHub/release governance for this repo

Before public release, configure repository settings so the workflow files are enforceable rather than advisory:

- protect `main` or create a ruleset requiring PRs;
- require the CI matrix jobs, dependency audit, package build/wheel-smoke, and CodeQL checks;
- require at least one review and stale-review dismissal;
- restrict direct pushes and force-pushes;
- require signed tags or a release ruleset for `v*`;
- enable GitHub Security Advisories and Dependabot security updates.

## Upgrades

Dependencies are intentionally constrained. Bump pins in a dedicated change with CI green, build verification, dependency audit, serve smoke, and a field-test re-run (`docs/demo.md`). `doctor` reads the tested pins from the installed package metadata, so it warns if the running environment drifts from them. The current dependency-audit exceptions (`PyNaCl==1.6.0` and `ecdsa`) are tracked in `docs/security.md` and should be removed only after compatible upstream Fetch/uAgents constraints are available.
