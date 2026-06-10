# Production Deployment

## Process model

One bridge per process. `serve` owns a dedicated event loop, starts the MCP
backend (stdio subprocess preferred), runs the uAgent server, and shuts down
gracefully on SIGINT/SIGTERM (exit code 0; the MCP child receives a clean
EOF). The two-process HTTP round trip including SIGTERM behavior is covered
by `tests/test_serve_http_roundtrip.py`.

## Secrets

- `UAGENT_SEED` comes from the environment only. The config loader rejects
  secret-shaped YAML values; mailbox mode fails closed without the seed; logs
  and audit redact seed-shaped strings.
- Use a dedicated agent seed. Fund the derived `fetch1...` wallet with only
  what Almanac registration needs.

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

Point `logging.audit_path` at `/var/lib/hermes-fetch-ai/audit.jsonl` and
rotate it with logrotate (`copytruncate`); the writer appends line-delimited
JSON and tolerates truncation between writes.

## Network egress

- Local/endpoint mode with `publish_manifest: false`: no mandatory egress.
  The agent probes the testnet ledger at startup; failures are logged and
  non-fatal.
- Hosted mode (mailbox/manifest): allow egress to Agentverse and the
  configured Fetch network (Almanac REST/gRPC, mailbox HTTPS).

## Going to mainnet (checklist)

1. Prove the deployment on `network: testnet` first (faucet-funded).
2. Set `agent.network` explicitly; never reuse a testnet seed casually.
3. Fund the `fetch1...` address for Almanac registration; uAgents' default
   registration policy pays automatically in hosted mode.
4. Keep `policy.public_tools` minimal (`skills_list` or empty); denylist wins.
5. Confirm `hermes_mcp.command` points at the Hermes environment's Python and
   that `HERMES_HOME` is set for the service user.

## Monitoring

- The audit JSONL is the operational signal: decisions, reasons, durations,
  sizes, truncation, send status. Alert on sustained `denied` spikes (probing)
  and on `send_status: failure`.
- `hermes-fetch-ai --version` and `doctor` are safe health probes.

## Upgrades

Dependencies are pinned exactly (`uagents==0.24.2`, `mcp==1.27.1`,
`uagents-adapter==0.6.2`). Bump pins in a dedicated change with CI green and
a field-test re-run (`docs/demo.md`); see `research/PRODUCTION_DECISION.md`
for the standing decision record.
