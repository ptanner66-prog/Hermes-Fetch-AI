# Demo

## Local CI demo

```bash
python -m hermes_fetch_ai.cli doctor
python -m hermes_fetch_ai.cli demo local
```

This uses fake MCP tools and an in-process direct call path. It must not require Agentverse, Almanac, ASI, mailbox setup, hosted accounts, or a real Hermes install.

## Hermes-backed local demo

Preferred path (isolated stdio subprocess of the Hermes tools MCP server):

```bash
python -m hermes_fetch_ai.cli doctor --config examples/hermes-stdio.yaml
python -m hermes_fetch_ai.cli serve --config examples/hermes-stdio.yaml
```

The `command` in `examples/hermes-stdio.yaml` must be the Python interpreter of the
environment where `hermes-agent` is installed, so that
`python -m agent.transports.hermes_tools_mcp_server` resolves.

Fallback path (in-process private server builder):

```bash
python -m hermes_fetch_ai.cli doctor --config examples/hermes-local.yaml
python -m hermes_fetch_ai.cli serve --config examples/hermes-local.yaml
```

If Hermes changes that private seam, run `python -m hermes_fetch_ai.cli probe-hermes` and use the output for upstream integration planning.

Note: `hermes mcp serve` exposes the Hermes conversations/messaging surface, not the
tools registry. The bridge never uses it; see `docs/security.md`.

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
