# Hermes plugin: `fetchai-bridge`

[`hermes-plugin/fetchai-bridge`](../hermes-plugin/fetchai-bridge) is a Hermes directory plugin (`plugin.yaml` + `__init__.py`) for Hermes 0.21.5 or later. It adds `hermes fetchai-bridge`, which runs this package's CLI, and ships an `operate` skill for the agent. It does not change Hermes core, and it adds nothing to the model's tool schema.

## Why a sidecar plugin

The bridge pins uAgents and `mcp==1.28.1` and supports Python 3.11/3.12. Hermes pins `mcp==2.0.0` (0.21.5 runs on Python 3.11; `main` has moved to 3.14), so the two cannot share one environment. A plugin that imported the bridge would have to install it into Hermes' environment, which is why the old `hermes_agent.plugins` entry point never worked with current Hermes.

The plugin is therefore a stdlib-only wrapper declared with `python_runtime: external`: Hermes installs nothing for it, and the bridge stays in its own environment (installed with `uv tool`). There is no `pyproject.toml` next to `plugin.yaml`, because Hermes would install one into its own environment.

## Install

```bash
# 1. The bridge, in its own environment (Python 3.11 or 3.12)
uv tool install --python 3.12 "hermes-fetch-ai @ git+https://github.com/ptanner66-prog/Hermes-Fetch-AI"

# 2. The plugin
hermes plugins install ptanner66-prog/Hermes-Fetch-AI/hermes-plugin/fetchai-bridge
hermes plugins enable fetchai-bridge

# 3. Check
hermes fetchai-bridge doctor
hermes fetchai-bridge demo local     # expect: echo result: hello
```

Once the catalog entry is merged, step 2 becomes `hermes plugins install fetchai-bridge` (see [`upstream-hermes-pr.md`](upstream-hermes-pr.md)).

To serve real Hermes tools, put `UAGENT_SEED` (at least 32 random characters) in `~/.hermes/.env` or the plugin's `uagent_seed` setting, copy [`examples/hermes-stdio.yaml`](../examples/hermes-stdio.yaml), leave `hermes_mcp.command` unset, and run:

```bash
hermes fetchai-bridge doctor --config /absolute/path/to/bridge.yaml
hermes fetchai-bridge serve --config /absolute/path/to/bridge.yaml
```

## What it registers

| Surface | Registered | Notes |
|---------|-----------|-------|
| CLI command | `hermes fetchai-bridge [ARGS...]` | Runs `hermes-fetch-ai` with the same arguments; no arguments shows the bridge's help. The exit status passes through. Ctrl-C reaches the bridge, which gets 30 seconds to shut down before it is killed. |
| Skill | `fetchai-bridge:operate` | Registered with `ctx.register_skill`; the agent loads it with `skill_view("fetchai-bridge:operate")`. Plugin skills are not listed in the system prompt or `hermes skills list`. Skipped on Hermes releases without plugin skills. |
| Tools, hooks, middleware | none | The catalog `capabilities` block is empty. |

## Settings

Stored under `plugins.entries.fetchai-bridge.settings` and shown in the Desktop app's plugin settings (`config_schema` in `plugin.yaml`):

| Key | Type | Purpose |
|-----|------|---------|
| `command` | `str` | Path to `hermes-fetch-ai` when it is not on PATH. Empty means search PATH. |
| `uagent_seed` | `secret` | Stored as `UAGENT_SEED` in Hermes' `.env`. Hermes loads `.env` into its environment and the bridge inherits it; the plugin never reads or prints the value. |

## How the bridge finds Hermes' tools server

`serve` starts Hermes' tools MCP server (`python -m agent.transports.hermes_tools_mcp_server`) as a stdio child process, and that needs Hermes' interpreter. When the plugin runs the bridge, it:

1. removes Hermes' Python variables (`PYTHONPATH`, `PYTHONHOME`, `PYTHONEXECUTABLE`, `__PYVENV_LAUNCHER__`, `VIRTUAL_ENV`) from the bridge's environment, because they would point the bridge's own interpreter at Hermes' packages (a managed Hermes runtime sets `PYTHONPATH` to its checkout and site-packages);
2. passes Hermes' interpreter (`sys.executable`) as `HERMES_FETCH_AI_HERMES_PYTHON`, and Hermes' `PYTHONPATH`, if any, as `HERMES_FETCH_AI_HERMES_PYTHONPATH`.

With `mode: stdio` and no `hermes_mcp.command`, the bridge starts the tools server with that interpreter and `PYTHONPATH`, plus `HERMES_QUIET=1` and `HERMES_REDACT_SECRETS=true`, which is how Hermes launches this server for its own integrations. An explicit `hermes_mcp.command` always wins. Without the hand-over and without a command, config validation fails with `hermes_mcp.command is required for stdio mode unless the bridge runs through hermes fetchai-bridge`.

The tools server still gets the bridge's short environment allowlist (`PATH`, `HOME`, `TMPDIR`, `HERMES_HOME`, locale, and the hand-over), so Hermes settings such as `HERMES_YOLO_MODE` never reach it.

## Running without the plugin

The plugin is a convenience, not a requirement. Set `hermes_mcp.command` to the Hermes environment's Python and run `hermes-fetch-ai serve --config ...` directly; that is also the path for supervised production services ([`production.md`](production.md)) and for `plugins.isolation: host`, under which Hermes skips plugin CLI commands.

## Disclosures

What a user should know before installing (catalog rule 13; also in the plugin README):

- One subprocess, without a shell: the `hermes-fetch-ai` executable, only when the user runs `hermes fetchai-bridge ...`. It inherits the environment, including `UAGENT_SEED`, minus Hermes' Python variables.
- No tools, hooks, or middleware; one read-only skill. The agent reaches the bridge only through Hermes' terminal tool, under Hermes' normal approvals. The skill tells the agent not to start `serve` unless asked.
- `serve` is long-running. It listens on the configured port, starts Hermes' tools MCP server as a child process, and contacts the Fetch.ai network or Agentverse only when its config enables that. By default remote agents see only `skills_list`.
- Nothing prompts or waits for input, so unattended runs do not hang. No telemetry, no self-updates, and no credentials other than `UAGENT_SEED`.

## Verification

- `tests/test_hermes_directory_plugin.py`: the manifest is catalog-ready (`python_runtime: external`, no Python dependencies, version matches the package), the plugin imports only the standard library, registration works with and without plugin-skill and settings support, arguments and exit codes pass through, the environment hand-over is clean, and a missing bridge prints install instructions.
- CI job `hermes-plugin`, against Hermes 0.21.5 (tag `v2026.9.24`) and a pinned `main`: installs Hermes from its checkout, runs `hermes plugins validate --install-deps` (the catalog admission check, including the security scan) and `hermes plugins doctor --ci`, enables the plugin and runs `hermes fetchai-bridge doctor` and `demo local`, then runs the stdio field test through the interpreter hand-over.
- Manually, on 2026-10-05 against `main` `bb236287`: installed from a `file://` URL with `--enable`; `UAGENT_SEED` from Hermes' `.env` reached the bridge; `serve` with `command` unset started Hermes' tools server, a remote signed client listed only `skills_list`, `skills_list` returned real skills, `web_search` was denied by policy, and Ctrl-C shut everything down cleanly.

## Boundaries

- No secrets in config examples. Production seed only via `UAGENT_SEED`.
- Replay metadata required for `CallTool` by default.
- `skills_list` is the only Hermes-backed demo-public tool.
- `skill_view`, `terminal`, browser, filesystem, messaging, approval, and conversations surfaces stay private unless an operator explicitly allowlists them for a known sender.
- The Hermes conversations/messaging MCP server (`hermes mcp serve`) is never bridged.
