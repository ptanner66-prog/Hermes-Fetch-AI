# Demo

## Local CI demo

```bash
python -m hermes_fetch_ai.cli doctor
python -m hermes_fetch_ai.cli demo local
```

This uses fake MCP tools and an in-process direct call path. It must not require Agentverse, Almanac, ASI, mailbox setup, hosted accounts, or a real Hermes install.

## Hermes-backed local demo

```bash
python -m hermes_fetch_ai.cli doctor --config examples/hermes-local.yaml
python -m hermes_fetch_ai.cli serve --config examples/hermes-local.yaml
```

This uses a private local Hermes server builder if available. If Hermes changes that private seam, run `python -m hermes_fetch_ai.cli probe-hermes` and use the output for upstream integration planning.

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
