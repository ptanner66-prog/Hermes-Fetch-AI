# Production Deployment

## Process model

One bridge per process. `serve` owns a dedicated event loop, starts the MCP backend (stdio subprocess preferred), runs the uAgent server, and shuts down gracefully on SIGINT/SIGTERM/SIGBREAK (exit code 0; the MCP child receives a clean EOF). The two-process HTTP round trip, signed message exchange, and graceful shutdown path are covered by `tests/test_serve_http_roundtrip.py`.

## Secrets

- `UAGENT_SEED` comes from the environment only. The config loader rejects production YAML seed values; mailbox/hosted mode fails closed without the seed; logs and audit redact seed-shaped strings.
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

Point `logging.audit_path` at `/var/lib/hermes-fetch-ai/audit.jsonl` and rotate it with logrotate (`copytruncate`); the writer appends line-delimited JSON and tolerates truncation between writes.

## Network egress

- Local/endpoint mode with `publish_manifest: false`: no mandatory egress for local tests. uAgents may probe the configured network at startup; failures are logged and non-fatal in local mode.
- Hosted mode (mailbox/manifest): allow egress to Agentverse and the configured Fetch network (Almanac REST/gRPC, mailbox HTTPS).

## Going to mainnet (checklist)

1. Prove the deployment on `network: testnet` first.
2. Set `agent.network` explicitly; never reuse a testnet seed casually.
3. Fund the derived `fetch1...` address only for Almanac registration needs.
4. Keep `policy.public_tools` empty or minimal (`skills_list` at most for Hermes-backed demos); denylist wins.
5. Confirm `hermes_mcp.command` points at the Hermes environment's Python and that `HERMES_HOME` is set for the service user.
6. Confirm callers attach replay metadata and treat replay denials as final, not retriable with the same request ID.
7. Run the full local gate and the gated field test before promoting a new config.

## Monitoring

The audit JSONL is the operational signal: decisions, reasons, durations, sizes, truncation, send status, and redacted sender fingerprints. Alert on:

- sustained `denied` spikes;
- `reason: replay detected` spikes;
- stale/future replay metadata spikes;
- `send_status: failure`;
- repeated `args exceed max_args_bytes` or URL/shell validation failures.

`hermes-fetch-ai --version` and `hermes-fetch-ai doctor` are safe health probes. Use `hermes fetchai doctor` only after the active Hermes installation has enabled and wired the plugin CLI.

## GitHub/release governance for this repo

Before public release, configure repository settings so the workflow files are enforceable rather than advisory:

- protect `main` or create a ruleset requiring PRs;
- require the CI matrix jobs, dependency audit, package build/wheel-smoke, and CodeQL checks;
- require at least one review and stale-review dismissal;
- restrict direct pushes and force-pushes;
- require signed tags or a release ruleset for `v*`;
- enable GitHub Security Advisories and Dependabot security updates.

## Upgrades

Dependencies are intentionally constrained. Bump pins in a dedicated change with CI green, build verification, dependency audit, serve smoke, and a field-test re-run (`docs/demo.md`). The current dependency-audit exception for `PyNaCl==1.6.0` is tracked in `docs/security.md` and should be removed only after compatible upstream Fetch/uAgents constraints are available.
