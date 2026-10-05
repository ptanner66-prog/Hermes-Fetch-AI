# Demo

## Local CI demo

```bash
python -m hermes_fetch_ai.cli doctor
python -m hermes_fetch_ai.cli demo local
```

This uses fake MCP tools and an in-process direct call path. It must not require Agentverse, Almanac, ASI, mailbox setup, hosted accounts, or a real Hermes install. The local demo sends replay metadata and exercises the same policy path as production calls.

## Hermes-backed local demo

Preferred path (isolated stdio subprocess of the Hermes tools MCP server). This config is production-shaped, so it needs a stable identity in `UAGENT_SEED` (at least 32 characters):

```bash
export UAGENT_SEED="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python -m hermes_fetch_ai.cli doctor --config examples/hermes-stdio.yaml
python -m hermes_fetch_ai.cli serve --config examples/hermes-stdio.yaml
```

The `command` in `examples/hermes-stdio.yaml` must be the Python interpreter of the environment where `hermes-agent` is installed, so that `python -m agent.transports.hermes_tools_mcp_server` resolves. If it does not, `serve` exits with `hermes backend: FAIL` and tells you to run that command by hand to see its error output.

Fallback path (in-process private server builder):

```bash
python -m hermes_fetch_ai.cli doctor --config examples/hermes-local.yaml
python -m hermes_fetch_ai.cli serve --config examples/hermes-local.yaml
```

If Hermes changes that private seam, run `python -m hermes_fetch_ai.cli probe-hermes` and use the output for upstream integration planning.

Note: `hermes mcp serve` exposes the Hermes conversations/messaging surface, not the tools registry. The bridge never uses it; see `docs/security.md`.

## Client call shape

`CallTool` clients must attach bridge replay/idempotency metadata under reserved args key `_hermes_fetch_ai`:

```json
{
  "tool": "echo",
  "args": {
    "text": "hello",
    "_hermes_fetch_ai": {
      "request_id": "client-generated-unique-id",
      "issued_at_ms": 1780000000000
    }
  }
}
```

The bridge removes `_hermes_fetch_ai` before validating and invoking the tool. Reuse of the same request ID by the same sender inside the TTL returns `replay detected` and does not invoke the tool again.

## Field test against a real hermes-agent install

One-time setup:

```bash
python -m venv /tmp/hermes-venv
/tmp/hermes-venv/bin/pip install -e "<hermes-agent checkout>[mcp]"
export HERMES_HOME=/tmp/hermes-home
mkdir -p "$HERMES_HOME/skills"   # copy at least one bundled skill in
```

Run the gated integration test:

```bash
HERMES_FETCH_FIELD_TEST=1 \
HERMES_FETCH_HERMES_PYTHON=/tmp/hermes-venv/bin/python \
python -m pytest tests/test_field_hermes_stdio.py -q
```

Observed behavior: the keyless server lists only tools whose prerequisites are met; the bridge shows an unknown sender `skills_list` only; `web_search` is denied by policy before any server call; `skills_list` returns real skill metadata.

Pitfalls:

- Follow the served inputSchema. hermes-agent v0.16.x wrapped every tool's arguments in one required `kwargs` object (send `{"kwargs": {}}` for `skills_list`); newer releases build flat schemas from each tool's JSON schema (send `{}` for `skills_list`, `{"query": "..."}` for `web_search`). Schema-following uAgent clients get this right automatically, and the field test handles both shapes.
- Replay metadata is in addition to the served schema and is stripped by the bridge before the schema check.
- `hermes_mcp.command` must be the Python interpreter of the environment where `hermes-agent` is installed. `HERMES_HOME` is forwarded to the subprocess by the bridge's environment allowlist.

## Agentverse mailbox manual demo

See [`agentverse-mailbox.md`](agentverse-mailbox.md). This tier is manual and not yet verified end to end. The mailbox config intentionally fails without `UAGENT_SEED`.

## Windows notes

PowerShell venv activation:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

Use `py -3.11` or `py -3.12` if plain `python` points to an unsupported version. Use `where hermes` to find a Hermes console script. Quote paths with spaces.
