# Demo

## Local CI demo

```bash
python -m hermes_fetch_ai.cli doctor
python -m hermes_fetch_ai.cli demo local
```

This uses fake MCP tools and an in-process uAgents dispatcher round trip. It must not require Agentverse, Almanac, ASI, mailbox setup, hosted accounts, funding, or a real Hermes install.

## Hermes MCP stdio demo

```bash
python -m hermes_fetch_ai.cli doctor --config examples/hermes-stdio.yaml --probe-backend
python -m hermes_fetch_ai.cli demo hermes --config examples/hermes-stdio.yaml
```

This proves the bridge can call Hermes' actual `hermes mcp serve` stdio surface through the same uAgents protocol path used by the fake local demo. The default config assumes the `hermes` console script is on PATH.

For a source checkout without a `hermes` console script, set a local command path and use the env config:

```powershell
$hermesRepo = "<path-to-hermes-agent-main>"
$env:HERMES_FETCH_HERMES_PYTHON = Join-Path $hermesRepo ".venv\Scripts\python.exe"
python -m hermes_fetch_ai.cli doctor --config examples/hermes-stdio-env.yaml --probe-backend
python -m hermes_fetch_ai.cli demo hermes --config examples/hermes-stdio-env.yaml
```

Expected output includes the bridge address, visible tool count, a `conversations_list result`, and audit event count. With no active Hermes gateway sessions, the result can legitimately be `{"count": 0, "conversations": []}`.

## Agentverse mailbox manual proof

The real Hermes mailbox config intentionally fails without `UAGENT_SEED` and keeps manifest publication off by default for safe startup. Do not put seeds in YAML, docs, commits, or chat.

Use the safe process-local seed entry flow from `research/NORMAL_HERMES_SECRET_TEST_RUNBOOK.md`; do not type a real seed into a command that will be saved in shell history.

First-time Agentverse mailbox linking uses the fake/Inspector config:

```powershell
python -m hermes_fetch_ai.cli serve --config examples/agentverse-mailbox.yaml
```

After the mailbox is linked, stop that process and start the real Hermes bridge:

```powershell
$hermesRepo = "<path-to-hermes-agent-main>"
$env:HERMES_FETCH_HERMES_PYTHON = Join-Path $hermesRepo ".venv\Scripts\python.exe"
# Enter UAGENT_SEED with Read-Host -AsSecureString as shown in the runbook.
python -m hermes_fetch_ai.cli doctor --config examples/agentverse-mailbox-hermes.yaml --probe-backend
python -m hermes_fetch_ai.cli serve --config examples/agentverse-mailbox-hermes.yaml
```

`demo mailbox --duration-seconds 30` is only a startup smoke window. `serve` is the live mode for remote mailbox traffic. Expected output prints the bridge address and startup status only. It must not print the seed. Hosted remote proof still requires the operator to create/link the Agentverse mailbox and capture a sanitized remote transcript; see `research/HOSTED_HOOKUP_EVIDENCE.md` and `research/OPERATOR_ACTIONS_TO_FINISH.md`.

## Payment dry-run demo

Payment support is optional and disabled by default. The dry-run demo uses official `uagents_core.contrib.protocols.payment` message models to prove request/commit/complete negotiation locally without wallet access, hosted remote payment negotiation, or fund movement.

```bash
python -m hermes_fetch_ai.cli demo payment-dry-run --config examples/payment-dry-run.yaml
```

Expected output includes a payment reference, accepted funds such as FET via `fet_direct`, `CompletePayment`, and `no real funds moved`.

## Windows notes

PowerShell venv activation:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

Use `py -3.11` or `py -3.12` if plain `python` points to an unsupported version. Use `where hermes` to find a Hermes console script. Quote paths with spaces.
