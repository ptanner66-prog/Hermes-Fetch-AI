# Full Hookup Status

Updated: 2026-05-17T03:35:34Z

Status: LOCAL FULL-HOOKUP PROOF GREEN; HOSTED AGENTVERSE PROOF BLOCKED ON OPERATOR ACTION.

This file supersedes earlier wording that said the repo was not Teknium-ready. The accurate status is narrower: the local/offline and real Hermes stdio bridge proof is now green, while hosted Agentverse mailbox proof remains operator-owned.

## Proven locally

- Fake MCP local demo passes through an in-process uAgents dispatcher round trip.
- Real Hermes stdio MCP backend is reachable from this machine through the Hermes source checkout venv.
- `hermes mcp serve` exposes 10 MCP tools to the probe.
- Hermes Fetch AI routes a `conversations_list` call through the uAgents bridge to the real Hermes MCP stdio backend.
- Payment dry-run negotiation uses official uAgents payment models and completes without settlement.
- Mailbox mode fails closed without operator seed.
- Test/lint/type/contamination gates pass.

## Commands run

```text
cmd //c ".\\.venv\\Scripts\\python.exe -m pytest -q"
cmd //c ".\\.venv\\Scripts\\python.exe -m ruff check ."
cmd //c ".\\.venv\\Scripts\\python.exe -m mypy src\\hermes_fetch_ai --ignore-missing-imports"
cmd //c ".\\.venv\\Scripts\\python.exe -m hermes_fetch_ai.cli doctor --contamination-scan"
cmd //c ".\\.venv\\Scripts\\python.exe -m hermes_fetch_ai.cli doctor --config examples\\hermes-stdio-env.yaml --probe-backend"
cmd //c ".\\.venv\\Scripts\\python.exe -m hermes_fetch_ai.cli demo hermes --config examples\\hermes-stdio-env.yaml"
cmd //c ".\\.venv\\Scripts\\python.exe -m hermes_fetch_ai.cli demo local"
cmd //c ".\\.venv\\Scripts\\python.exe -m hermes_fetch_ai.cli demo payment-dry-run --config examples\\payment-dry-run.yaml"
env -u UAGENT_SEED cmd //c ".\\.venv\\Scripts\\python.exe -m hermes_fetch_ai.cli doctor --config examples\\agentverse-mailbox-hermes.yaml --probe-backend"
env -u UAGENT_SEED cmd //c ".\\.venv\\Scripts\\python.exe -m hermes_fetch_ai.cli demo mailbox --config examples\\agentverse-mailbox-hermes.yaml --duration-seconds 1"
```

Observed:

- `77 passed in 17.94s`
- `All checks passed!`
- `Success: no issues found in 20 source files`
- `contamination: ok`
- `backend: ok: 10 tools`
- Hermes stdio demo returned `{"count": 0, "conversations": []}` through the bridge.
- Local demo returned `echo result: hello`.
- Payment dry-run returned `CompletePayment` and explicitly did not settle funds.
- Mailbox commands without `UAGENT_SEED` exited 1 with the expected missing-seed blocker.

## Still not proven

- Hosted Agentverse mailbox registration and linking.
- Remote uAgent -> Agentverse/Mailbox -> Hermes Fetch AI -> Hermes MCP -> response transcript.
- Agentverse/Inspector UI evidence or remote transcript evidence.
- Almanac/manifest hosted lookup evidence.
- Upstream Hermes PR patch.

## Operator action needed

To prove the hosted path, the operator needs:

1. Agentverse/Fetch account access.
2. A stable uAgent seed set only in the operator shell.
3. A mailbox-capable Agentverse agent entry linked to the bridge address.
4. A remote uAgent that sends the official MCP protocol messages to the bridge.
5. Non-secret transcript/manifest evidence.

Stop if any funding, registration fee, or production deployment prompt appears. Record the prompt and get explicit operator approval before proceeding.
