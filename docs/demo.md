# Demo

## Local CI demo

```bash
python -m hermes_fetch_ai.cli doctor
python -m hermes_fetch_ai.cli demo local
```

This uses fake MCP tools and an in-process uAgents dispatcher round trip. It must not require Agentverse, Almanac, ASI, mailbox setup, hosted accounts, or a real Hermes install.

## Hermes MCP stdio demo

```bash
python -m hermes_fetch_ai.cli doctor --config examples/hermes-stdio.yaml --probe-backend
python -m hermes_fetch_ai.cli demo hermes --config examples/hermes-stdio.yaml
```

This proves the bridge can call Hermes' actual `hermes mcp serve` stdio surface through the same uAgents protocol path used by the fake local demo. The default config assumes the `hermes` console script is on PATH.

For a source checkout without a `hermes` console script, set a local command path and use the env config:

```powershell
$env:HERMES_FETCH_HERMES_PYTHON = "C:\Users\you\path\to\hermes-agent-main\.venv\Scripts\python.exe"
python -m hermes_fetch_ai.cli doctor --config examples/hermes-stdio-env.yaml --probe-backend
python -m hermes_fetch_ai.cli demo hermes --config examples/hermes-stdio-env.yaml
```

Expected output includes the bridge address, visible tool count, a `conversations_list result`, and audit event count. With no active Hermes gateway sessions, the result can legitimately be `{"count": 0, "conversations": []}`.

## Agentverse mailbox manual demo

See `research/FETCH_ACCOUNT_REQUIREMENTS.md`. The mailbox config intentionally fails without `UAGENT_SEED`.

## Windows notes

PowerShell venv activation:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

Use `py -3.11` or `py -3.12` if plain `python` points to an unsupported version. Use `where hermes` to find a Hermes console script. Quote paths with spaces.
