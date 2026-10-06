# Hermes plugin: `fetchai-bridge`

[`hermes-plugin/fetchai-bridge`](../hermes-plugin/fetchai-bridge) is a Hermes directory plugin (`plugin.yaml` plus `__init__.py`). It requires Hermes 0.21.5 or later; CI tests 0.21.5 and a pinned `main`. It adds `hermes fetchai-bridge`, which runs this package's CLI, and ships an `operate` skill for the agent. It does not change Hermes core and adds nothing to the model's tool schema.

## Why a sidecar plugin

Hermes pins `mcp==2.0.0` (0.21.5 runs on Python 3.11; `main` has moved to 3.14). The bridge pins `mcp==1.28.1`, the version it is tested with, and supports Python 3.11/3.12, so the two cannot share an environment. A plugin that imported the bridge would have to install it into Hermes' environment, which is why the old `hermes_agent.plugins` entry point never worked with current Hermes.

The plugin is therefore a stdlib-only wrapper declared with `python_runtime: external`: Hermes installs nothing for it, and the bridge stays in its own environment (installed with `uv tool` or pipx). There is no `pyproject.toml` next to `plugin.yaml`, because Hermes would install one into its own environment.

## Install

```bash
# 1. The bridge, in its own environment (Python 3.11 or 3.12)
uv tool install --python 3.12 "hermes-fetch-ai @ git+https://github.com/ptanner66-prog/Hermes-Fetch-AI"

# 2. The plugin
hermes plugins install ptanner66-prog/Hermes-Fetch-AI/hermes-plugin/fetchai-bridge
hermes plugins enable fetchai-bridge

# 3. Check
hermes fetchai-bridge doctor
hermes fetchai-bridge demo local      # expect: echo result: hello
hermes fetchai-bridge probe-hermes    # expect: hermes_tools_server: importable
```

Once the catalog entry is merged, step 2 becomes `hermes plugins install fetchai-bridge` (see [`upstream-hermes-pr.md`](upstream-hermes-pr.md)). To serve real Hermes tools, follow "Connect real Hermes tools" in the [README](../README.md#connect-real-hermes-tools).

## What it registers

| Surface | Registered | Notes |
|---------|-----------|-------|
| CLI command | `hermes fetchai-bridge [ARGS...]` | Runs `hermes-fetch-ai` with the same arguments; with no arguments it shows the bridge's help. The exit status passes through. Ctrl-C reaches the bridge, which gets 30 seconds to shut down before it is killed. Hermes handles a leading `--version` itself; `hermes fetchai-bridge doctor` prints the bridge's version. |
| Skill | `fetchai-bridge:operate` | Registered with `ctx.register_skill`; the agent loads it with `skill_view("fetchai-bridge:operate")`. Plugin skills are not listed in the system prompt or in `hermes skills list`. Skipped on Hermes releases without plugin skills. |
| Tools, hooks, middleware | none | The catalog entry's `capabilities` lists are empty. |

## Settings

Stored under `plugins.entries.fetchai-bridge.settings` and shown in the Desktop app's plugin settings (`config_schema` in `plugin.yaml`):

| Key | Type | Purpose |
|-----|------|---------|
| `command` | `str` | Path to `hermes-fetch-ai` when it is not on PATH. Empty means search PATH. |
| `uagent_seed` | `secret` | Stored as `UAGENT_SEED` in `$HERMES_HOME/.env`. Hermes loads that file into its environment, and the plugin passes the value to the bridge; the plugin never prints it. |

## How the plugin runs the bridge

The bridge gets an allowlisted environment, not Hermes' whole one: `UAGENT_SEED`, `HERMES_HOME`, `PATH`, `HOME`, locale, temp-directory, proxy and certificate settings, and the Windows essentials (`BRIDGE_ENV` in [`__init__.py`](../hermes-plugin/fetchai-bridge/__init__.py)). Everything else Hermes loaded from its `.env`, such as model-provider API keys, stays out.

`serve` starts Hermes' tools MCP server (`python -m agent.transports.hermes_tools_mcp_server`) as a stdio child process, and that needs Hermes' interpreter. The plugin passes Hermes' interpreter (`sys.executable`) as `HERMES_FETCH_AI_HERMES_PYTHON`, and Hermes' `PYTHONPATH`, if any, as `HERMES_FETCH_AI_HERMES_PYTHONPATH`. Hermes' own Python variables are not passed as such, because they would point the bridge's interpreter at Hermes' packages (a managed Hermes runtime sets `PYTHONPATH` to its checkout and site-packages).

With `mode: stdio` and no `hermes_mcp.command`, the bridge starts the tools server with that interpreter and `PYTHONPATH`, plus `HERMES_QUIET=1` and `HERMES_REDACT_SECRETS=true`, which is how Hermes launches this server for its own integrations. An explicit `hermes_mcp.command` always wins. Without either, config validation fails with `hermes_mcp.command is required for stdio mode unless the bridge runs through hermes fetchai-bridge`. `probe-hermes` checks the handed-over interpreter the same way.

The tools server itself gets an even shorter allowlist (`PATH`, `HOME`, `TMPDIR`, `HERMES_HOME`, locale, and the hand-over), so Hermes settings such as `HERMES_YOLO_MODE` never reach it.

## Running without the plugin

The plugin is a convenience, not a requirement. Set `hermes_mcp.command` to the Hermes environment's Python and run `hermes-fetch-ai serve --config ...` directly. That is the path for supervised services ([`production.md`](production.md)), and for Hermes builds that run plugins with `plugins.isolation: host` (on `main` after 0.21.5), which skip plugin CLI commands.

## Disclosures

What the plugin and the bridge do (network listeners, outbound calls, credentials, files, wallet spending) is listed in "What this plugin does" in the [plugin README](../hermes-plugin/fetchai-bridge/README.md), which is the copy the Hermes catalog page shows.

## Verification

- `tests/test_hermes_directory_plugin.py`: the manifest is catalog-ready (`python_runtime: external`, no Python dependencies, version matches the package); the plugin imports only the standard library; registration works with and without plugin-skill and settings support; arguments and exit codes pass through; the bridge's environment is allowlisted (provider API keys stay out) and carries the interpreter hand-over; a missing bridge prints install instructions; and the catalog entry draft matches `plugin.yaml`.
- CI job `hermes-plugin`, against Hermes 0.21.5 (tag `v2026.9.24`) and a pinned `main`: installs Hermes from its checkout; `hermes plugins validate --install-deps` (the catalog admission check, including the install security scan) and `hermes plugins doctor --ci` must pass; enables the plugin and runs `hermes fetchai-bridge doctor` and `demo local`; then runs the stdio field test through the interpreter hand-over.
- By hand on 2026-10-06, against both versions: the security scan's verdict was `safe`, and `hermes fetchai-bridge probe-hermes` reported `importable`. On 2026-10-05, against `main` `bb236287`: installed from a `file://` URL with `--enable`; `UAGENT_SEED` from Hermes' `.env` reached the bridge; `serve` with `command` unset started Hermes' tools server; a remote signed client saw only `skills_list`, which returned real skills; `web_search` was denied by policy; and Ctrl-C shut everything down cleanly.
