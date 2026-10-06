# Demo

## Local demo (fake tools, no network)

```bash
hermes-fetch-ai doctor
hermes-fetch-ai demo local
```

This uses the two built-in fake tools and uAgents' in-process message dispatcher. It needs no Agentverse account, Almanac registration, seed, or Hermes install, and it makes no network calls (`tests/test_security_defaults.py` checks that it never contacts the Almanac). The demo sends replay-protection metadata and goes through the same policy path as real calls, and it writes its audit log to a temporary file.

To call a bridge over HTTP the way a remote agent would, start one with the same fake tools and run the example client:

```bash
hermes-fetch-ai serve --config examples/local-direct.yaml
# logs: Starting agent with address: agent1q...
python examples/call_bridge.py agent1q... http://127.0.0.1:8001/submit
```

The client lists the bridge's tools and calls `echo`. `local-direct.yaml` uses a new random identity on every start, so copy the address from the log each time.

## Hermes-backed demo

The production shape runs Hermes' tools MCP server as a stdio subprocess. `examples/hermes-stdio.yaml` needs a stable identity in `UAGENT_SEED` (at least 32 characters); generate one with `python -c 'import secrets; print(secrets.token_hex(32))'`.

Through the Hermes plugin ([`hermes-plugin.md`](hermes-plugin.md)), put `UAGENT_SEED` in `$HERMES_HOME/.env` (default `~/.hermes/.env`) and leave `hermes_mcp.command` unset; the plugin hands the bridge Hermes' own interpreter:

```bash
hermes fetchai-bridge probe-hermes
hermes fetchai-bridge doctor --config /absolute/path/to/bridge.yaml
hermes fetchai-bridge serve --config /absolute/path/to/bridge.yaml
```

Without the plugin, set `hermes_mcp.command` to the Python interpreter of the environment where `hermes-agent` is installed (so that `python -m agent.transports.hermes_tools_mcp_server` resolves), and run the bridge directly:

```bash
export UAGENT_SEED="$(python -c 'import secrets; print(secrets.token_hex(32))')"
hermes-fetch-ai doctor --config bridge.yaml
hermes-fetch-ai serve --config bridge.yaml
```

If the tools server cannot start, `serve` exits with `hermes backend: FAIL` and names the command to run by hand to see the error.

The in-process mode (`examples/hermes-local.yaml`) imports Hermes' tools server into the bridge's own process. It needs Hermes and the bridge in one environment, which works with hermes-agent v0.16.x but not with current releases, which pin mcp 2.0.

## Client call shape

A `CallTool` message carries the tool's arguments plus replay-protection metadata under the reserved key `_hermes_fetch_ai`:

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

The rules for the metadata are in [`production.md`](production.md#replay-protection-contract).

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

Run the test:

```bash
HERMES_FETCH_FIELD_TEST=1 \
HERMES_FETCH_HERMES_PYTHON=/tmp/hermes-venv/bin/python \
python -m pytest tests/test_field_hermes_stdio.py -q
```

The test reads Hermes' interpreter from `HERMES_FETCH_HERMES_PYTHON`, leaves `hermes_mcp.command` unset, and hands the interpreter to the bridge as `HERMES_FETCH_AI_HERMES_PYTHON`, as the plugin does. It checks that an unknown sender sees only `skills_list`, that `skills_list` returns real skill data, and that `web_search` is denied by policy before any call reaches the server.

Last run on 2026-10-06 against Hermes 0.21.5 (Python 3.11, mcp 2.0.0) and hermes-agent `main` (`bb236287`, Python 3.14.8, mcp 2.0.0): `1 passed` on both. The bridge's mcp 1.28.1 client negotiates MCP protocol `2025-11-25`, which the mcp 2.0 server accepts. Without provider credentials, the server offered `web_search`, `web_extract`, `skill_view`, `skills_list`, and `text_to_speech`.

Callers must follow each tool's input schema. hermes-agent v0.16.x wrapped every tool's arguments in one required `kwargs` object (send `{"kwargs": {}}` for `skills_list`); newer releases use flat arguments (`{}` for `skills_list`, `{"query": "..."}` for `web_search`). The field test handles both. Replay-protection metadata comes on top of the tool's schema; the bridge strips it before the schema check.

## Agentverse mailbox demo

See [`agentverse-mailbox.md`](agentverse-mailbox.md). This tier is manual and not yet verified end to end. Its config refuses to start without `UAGENT_SEED`.

## Windows notes

PowerShell setup:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

Use `py -3.11` or `py -3.12` if plain `python` points to an unsupported version. To find Hermes' command, use `Get-Command hermes` (in PowerShell, `where` means `Where-Object`). Quote paths that contain spaces.
