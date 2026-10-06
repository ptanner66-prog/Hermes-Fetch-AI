# fetchai-bridge

A Hermes plugin for [Hermes Fetch AI](https://github.com/ptanner66-prog/Hermes-Fetch-AI), the policy-aware bridge that lets Fetch.ai uAgents call an allowlisted subset of Hermes tools.

The bridge pins uAgents and mcp 1.x and runs on Python 3.11/3.12, so it cannot share Hermes' environment. This plugin is a thin, stdlib-only wrapper (`python_runtime: external`): it adds a `hermes fetchai-bridge` command that runs the separately installed bridge, and it ships an `operate` skill for the agent.

Requires Hermes 0.21.5 or later. CI checks it against Hermes 0.21.5 and a pinned `main`.

## Install

1. Install the bridge in its own environment:

   ```bash
   uv tool install --python 3.12 "hermes-fetch-ai @ git+https://github.com/ptanner66-prog/Hermes-Fetch-AI"
   ```

2. Install and enable the plugin:

   ```bash
   hermes plugins install ptanner66-prog/Hermes-Fetch-AI/hermes-plugin/fetchai-bridge
   hermes plugins enable fetchai-bridge
   ```

3. Check it:

   ```bash
   hermes fetchai-bridge doctor
   hermes fetchai-bridge demo local     # expect: echo result: hello
   ```

## Use

`hermes fetchai-bridge <args>` passes its arguments unchanged to `hermes-fetch-ai`:

```bash
hermes fetchai-bridge doctor --config /absolute/path/to/bridge.yaml
hermes fetchai-bridge serve --config /absolute/path/to/bridge.yaml
hermes fetchai-bridge probe-hermes
```

To serve real Hermes tools, add `UAGENT_SEED` (at least 32 random characters) to Hermes' `.env` or the `uagent_seed` setting, copy [`examples/hermes-stdio.yaml`](../../examples/hermes-stdio.yaml), and leave `hermes_mcp.command` unset: the plugin tells the bridge which Python runs this Hermes, and `serve` starts Hermes' tools MCP server with it, the way Hermes starts that server itself. The agent can load the bundled skill with `skill_view("fetchai-bridge:operate")`.

## Settings

Under `plugins.entries.fetchai-bridge.settings` (also shown in the Desktop app's plugin settings):

| Key | Purpose |
|-----|---------|
| `command` | Path to `hermes-fetch-ai` if it is not on PATH |
| `uagent_seed` | Secret, stored as `UAGENT_SEED` in Hermes' `.env`; the bridge's stable identity for `serve` (at least 32 random characters) |

## What this plugin does

- Runs one subprocess, without a shell: the `hermes-fetch-ai` executable, only when you run `hermes fetchai-bridge ...`. It inherits your environment, including `UAGENT_SEED`, minus Hermes' Python variables (`PYTHONPATH`, `PYTHONHOME`, `VIRTUAL_ENV`, ...). Hermes' interpreter path and `PYTHONPATH` are passed as `HERMES_FETCH_AI_HERMES_PYTHON` and `HERMES_FETCH_AI_HERMES_PYTHONPATH` instead.
- Registers no tools, hooks, or middleware, and ships one read-only skill. The agent reaches the bridge only through Hermes' terminal tool, under Hermes' normal approvals.
- `hermes fetchai-bridge serve` is long-running. It listens on the configured port, starts Hermes' tools MCP server as its own child process, and contacts the Fetch.ai network or Agentverse only when its config enables that. By default only `skills_list` is exposed to remote agents.
- The tools server gets a short allowlisted environment (`PATH`, `HOME`, `TMPDIR`, `HERMES_HOME`, locale, and the interpreter hand-over), so settings such as `HERMES_YOLO_MODE` never reach it.
- Nothing prompts or waits for input. No telemetry, no self-updates, and no other credentials are read.
- Under `plugins.isolation: host`, Hermes skips plugin CLI commands; run `hermes-fetch-ai` directly instead.

## License

MIT
