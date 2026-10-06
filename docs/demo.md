# Demo

## Local CI demo

```bash
python -m hermes_fetch_ai.cli doctor
python -m hermes_fetch_ai.cli demo local
```

This uses fake MCP tools and an in-process direct call path. It needs no Agentverse, Almanac, ASI, mailbox setup, hosted account, or real Hermes install, and it makes no network calls (`tests/test_security_defaults.py` checks that it never contacts the Almanac). The local demo sends replay metadata and exercises the same policy path as production calls.

## Hermes-backed local demo

Preferred path: an isolated stdio subprocess of the Hermes tools MCP server. `examples/hermes-stdio.yaml` is production-shaped, so it needs a stable identity in `UAGENT_SEED` (at least 32 characters). Generate one with `python -c 'import secrets; print(secrets.token_hex(32))'`.

Through the Hermes plugin ([`native-hermes-plugin.md`](native-hermes-plugin.md)), put `UAGENT_SEED` in `~/.hermes/.env` and leave `hermes_mcp.command` unset; the plugin hands the bridge Hermes' own interpreter:

```bash
hermes fetchai-bridge doctor --config /absolute/path/to/examples/hermes-stdio.yaml
hermes fetchai-bridge serve --config /absolute/path/to/examples/hermes-stdio.yaml
```

Without the plugin, copy the example, set `hermes_mcp.command` to the Python interpreter of the environment where `hermes-agent` is installed (so that `python -m agent.transports.hermes_tools_mcp_server` resolves), and run the bridge directly:

```bash
export UAGENT_SEED="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python -m hermes_fetch_ai.cli doctor --config bridge.yaml
python -m hermes_fetch_ai.cli serve --config bridge.yaml
```

If the tools server cannot start, `serve` exits with `hermes backend: FAIL` and tells you to run that command by hand to see its error output.

Fallback path (in-process private server builder). It needs Hermes and the bridge in one environment, which works with hermes-agent v0.16.x but not with current releases, which pin mcp 2.0:

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

CI runs this test in its `hermes-plugin` job against Hermes 0.21.5 and a pinned `main`. To run it yourself, one-time setup:

```bash
# Use the Python version in the checkout's .python-version:
# 3.11 for the 0.21.5 release (tag v2026.9.24), 3.14 for main.
uv venv -p 3.11 /tmp/hermes-venv
uv pip install --python /tmp/hermes-venv/bin/python -e "<hermes-agent checkout>[mcp]"
export HERMES_HOME=/tmp/hermes-home
mkdir -p "$HERMES_HOME/skills"   # copy at least one bundled skill in
```

hermes-agent only supports installs from a checkout. On a Python older than its checkout asks for, the install appears to succeed but skips Hermes' dependencies, and `serve` then fails with `hermes backend: FAIL` (the server exits with `No module named 'ruamel'`).

Run the gated integration test:

```bash
HERMES_FETCH_FIELD_TEST=1 \
HERMES_FETCH_HERMES_PYTHON=/tmp/hermes-venv/bin/python \
python -m pytest tests/test_field_hermes_stdio.py -q
```

Observed behavior: the keyless server lists only tools whose prerequisites are met; the bridge shows an unknown sender `skills_list` only; `web_search` is denied by policy before any server call; `skills_list` returns real skill metadata.

Last run on 2026-10-06 against Hermes 0.21.5 (Python 3.11, mcp 2.0.0) and hermes-agent `main` (`bb236287`, Python 3.14.8, mcp 2.0.0): `1 passed` on both. The bridge's mcp 1.28.1 client negotiates MCP protocol `2025-11-25`, which the mcp 2.0 server still accepts. Without credentials the server exposed `web_search`, `web_extract`, `skill_view`, `skills_list`, and `text_to_speech`.

Pitfalls:

- Follow the served inputSchema. hermes-agent v0.16.x wrapped every tool's arguments in one required `kwargs` object (send `{"kwargs": {}}` for `skills_list`); newer releases build flat schemas from each tool's JSON schema (send `{}` for `skills_list`, `{"query": "..."}` for `web_search`). Schema-following uAgent clients get this right automatically, and the field test handles both shapes.
- Replay metadata is in addition to the served schema and is stripped by the bridge before the schema check.
- The test leaves `hermes_mcp.command` unset and passes `HERMES_FETCH_HERMES_PYTHON` the way the Hermes plugin does (`HERMES_FETCH_AI_HERMES_PYTHON`), so it also covers the plugin's interpreter hand-over. When you run `hermes-fetch-ai serve` yourself, set `hermes_mcp.command` to the Python interpreter of the environment where `hermes-agent` is installed. `HERMES_HOME` is forwarded to the subprocess by the bridge's environment allowlist.

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
