# Hermes plugin: `fetchai-bridge`

[`hermes-plugin/fetchai-bridge`](../hermes-plugin/fetchai-bridge) is a Hermes directory plugin (`plugin.yaml` plus `__init__.py`). It requires Hermes 0.21.5 or later; CI tests 0.21.5 and a pinned `main`. It adds `hermes fetchai-bridge`, which installs, sets up, and runs this package's CLI; `operate` and `buy` skills for the agent; and four buying tools, off until the user turns them on. It does not change Hermes core.

## Why a sidecar plugin

Hermes pins `mcp==2.0.0` (0.21.5 runs on Python 3.11; `main` has moved to 3.14). The bridge pins `mcp==1.28.1`, the version it is tested with, and supports Python 3.11/3.12, so the two cannot share an environment. A plugin that imported the bridge would have to install it into Hermes' environment, which is why the old `hermes_agent.plugins` entry point never worked with current Hermes.

The plugin is therefore a stdlib-only wrapper declared with `python_runtime: external`: Hermes installs nothing for it, and the bridge stays in its own environment (installed with `uv tool` or pipx). There is no `pyproject.toml` next to `plugin.yaml`, because Hermes would install one into its own environment.

## Install

```bash
hermes plugins install ptanner66-prog/Hermes-Fetch-AI/hermes-plugin/fetchai-bridge
hermes plugins enable fetchai-bridge
hermes fetchai-bridge install       # the bridge, in its own environment; asks first
hermes fetchai-bridge setup         # the agent's key and the owner's choices
hermes fetchai-bridge start
hermes fetchai-bridge status
```

Once the catalog entry is merged, the first line becomes `hermes plugins install fetchai-bridge` (see [`upstream-hermes-pr.md`](upstream-hermes-pr.md)). To let other agents call Hermes tools, see [`hermes-tools.md`](hermes-tools.md).

### What `install` and `setup` do

- `install` runs `uv tool install --force --python 3.12 "hermes-fetch-ai @ git+https://github.com/ptanner66-prog/Hermes-Fetch-AI@v<plugin version>"` (or the same with pipx) after showing the command and asking, or with `--yes`; without a terminal and without `--yes` it does nothing. A bridge of the plugin's version is left alone. The pin is the git tag of the plugin's version (`PLUGIN_VERSION` in `__init__.py`, equal to `plugin.yaml`'s), so releases tag `v<version>`; nothing updates itself (catalog rule 3).
- `setup` installs the bridge first if needed. When `UAGENT_SEED` is not set, it makes one (`secrets.token_hex(32)`) and keeps it in Hermes' `.env` with Hermes' own writer, `hermes_cli.config.save_env_value`, then checks Hermes kept it; a Hermes whose `.env` it may not change stops setup with instructions. It offers to keep an Agentverse API key the same way. Both are this plugin's own `config_schema` secrets. It then runs the bridge's `setup` (the questions), which reports back whether the owner chose buying, and offers to turn on this plugin's `buyer_tools` setting with `ctx.set_config`. It never prints the key.
- The plugin passes its version to the bridge (`HERMES_FETCH_AI_PLUGIN_VERSION`), and the bridge says when the two differ.

## What it registers

| Surface | Registered | Notes |
|---------|-----------|-------|
| CLI command | `hermes fetchai-bridge [ARGS...]` | `install` and `setup` are the plugin's own (above); everything else runs `hermes-fetch-ai` with the same arguments; with no arguments it shows the bridge's help. The exit status passes through. Ctrl-C reaches the bridge, which gets 30 seconds to shut down before it is killed. Hermes handles a leading `--version` itself; `hermes fetchai-bridge doctor` prints the bridge's version. |
| Skills | `fetchai-bridge:operate`, `fetchai-bridge:buy` | Registered with `ctx.register_skill`; the agent loads them with `skill_view("fetchai-bridge:operate")`. Plugin skills are not listed in the system prompt or in `hermes skills list`. Skipped on Hermes releases without plugin skills. |
| Tools | `fetchai_find_agents`, `fetchai_message_agent`, `fetchai_read_replies`, `fetchai_pay` (toolset `fetchai`) | Declared in `provides_tools` and always registered; their `check_fn` keeps them unavailable until the `buyer_tools` setting is on. Each refuses while YOLO mode is on (`tools.approval.is_approval_bypass_active`), or when Hermes cannot say. `fetchai_pay` asks the user with `tools.approval_prompt.request_elicitation_consent` and pays only on "accept" ([`buying.md`](buying.md)). Each runs `hermes-fetch-ai buyer ... --json` with the bridge's environment allowlist; searches and messages travel on standard input, never in the command line. |
| Hooks, middleware | none | The catalog entry's `provides_hooks` and `provides_middleware` are empty. |

## Settings

Stored under `plugins.entries.fetchai-bridge.settings` and shown in the Desktop app's plugin settings (`config_schema` in `plugin.yaml`):

| Key | Type | Purpose |
|-----|------|---------|
| `command` | `str` | Path to `hermes-fetch-ai` when it is not on PATH. Empty means search PATH. |
| `uagent_seed` | `secret` | Stored as `UAGENT_SEED` in `$HERMES_HOME/.env`. Hermes loads that file into its environment, and the plugin passes the value to the bridge; the plugin never prints it. |
| `agentverse_api_key` | `secret` | Stored as `AGENTVERSE_API_KEY` in `$HERMES_HOME/.env`, and passed to the bridge the same way. Only `agentverse register` uses it ([`asi-one.md`](asi-one.md)), and `buyer find` sends it to Agentverse's search if set (the search works without it). |
| `buyer_tools` | `bool` | Off by default. On: Hermes may use the four buying tools; every payment still asks the user. |
| `config` | `str` | The config file `serve` runs with, passed to the `buyer` commands; needed only when it sets `payments.state_dir`. |

## How the plugin runs the bridge

The bridge gets an allowlisted environment, not Hermes' whole one: `UAGENT_SEED`, `AGENTVERSE_API_KEY`, `HERMES_HOME`, `PATH`, `HOME`, locale, temp-directory, proxy and certificate settings, and the Windows essentials (`BRIDGE_ENV` in [`__init__.py`](../hermes-plugin/fetchai-bridge/__init__.py)). Everything else Hermes loaded from its `.env`, such as model-provider API keys, stays out.

`serve` starts Hermes' tools MCP server (`python -m agent.transports.hermes_tools_mcp_server`) as a stdio child process, and that needs Hermes' interpreter. The plugin passes Hermes' interpreter (`sys.executable`) as `HERMES_FETCH_AI_HERMES_PYTHON`, and Hermes' `PYTHONPATH`, if any, as `HERMES_FETCH_AI_HERMES_PYTHONPATH`. Hermes' own Python variables are not passed as such, because they would point the bridge's interpreter at Hermes' packages (a managed Hermes runtime sets `PYTHONPATH` to its checkout and site-packages).

With `mode: stdio` and no `hermes_mcp.command`, the bridge starts the tools server with that interpreter and `PYTHONPATH`, plus `HERMES_QUIET=1` and `HERMES_REDACT_SECRETS=true`, which is how Hermes launches this server for its own integrations. An explicit `hermes_mcp.command` always wins. Without either, config validation fails with `hermes_mcp.command is required for stdio mode unless the bridge runs through hermes fetchai-bridge`. `probe-hermes` checks the handed-over interpreter the same way.

A service run by a guest Hermes ([`guest-hermes.md`](guest-hermes.md)) uses the same hand-over: unless its runner sets `python`, each request runs `python -m hermes_cli.main chat` with Hermes' interpreter and `PYTHONPATH`, in a throwaway Hermes home of its own, never yours.

The tools server itself gets an even shorter allowlist (`PATH`, `HOME`, `TMPDIR`, `HERMES_HOME`, locale, and the hand-over), so Hermes settings such as `HERMES_YOLO_MODE` never reach it.

## Running without the plugin

The plugin is a convenience, not a requirement. Set `hermes_mcp.command` to the Hermes environment's Python and run `hermes-fetch-ai serve --config ...` directly. That is the path for supervised services ([`production.md`](production.md)), and for Hermes builds that run plugins with `plugins.isolation: host` (on `main` after 0.21.5), which skip plugin CLI commands.

## Disclosures

What the plugin and the bridge do (network listeners, outbound calls, credentials, files, wallet spending) is listed in "What this plugin does" in the [plugin README](../hermes-plugin/fetchai-bridge/README.md), which is the copy the Hermes catalog page shows.

## Verification

- `tests/test_hermes_directory_plugin.py`: the manifest is catalog-ready (`python_runtime: external`, no Python dependencies, version matches the package); the plugin imports only the standard library; registration works with and without plugin-skill and settings support; arguments and exit codes pass through; the bridge's environment is allowlisted (provider API keys stay out) and carries the interpreter hand-over; a missing bridge prints install instructions; and the catalog entry draft matches `plugin.yaml`.
- CI job `hermes-plugin`, against Hermes 0.21.5 (tag `v2026.9.24`) and a pinned `main`: installs Hermes from its checkout; `hermes plugins validate --install-deps` (the catalog admission check, including the install security scan) and `hermes plugins doctor --ci` must pass; enables the plugin and runs `hermes fetchai-bridge doctor` and `demo local`; then runs the stdio field test through the interpreter hand-over, the guest Hermes field test, and the buying-guard field test (the plugin loaded inside Hermes: YOLO seen through `HERMES_YOLO_MODE` and `approvals.mode: off`; the payment prompt declines when nobody can answer; `save_secret` puts `UAGENT_SEED` in Hermes' `.env`, mode 0600).
- `tests/test_plugin_setup.py`: `install` asks first, never waits without a terminal, pins the plugin's version, and passes uv only the allowlisted environment (plus `UV_*`/`PIPX_*`); `setup` makes and keeps the key through Hermes, offers the Agentverse key and the buying tools, and stops when Hermes cannot keep the key; the bridge notes a version mismatch.
- By hand on 2026-10-06, against both versions, in a fresh Hermes home: `hermes fetchai-bridge setup --answers ...` made a key and kept it in Hermes' `.env`, the bridge's setup wrote its config, and `start`, `status`, and `stop` ran the agent in the background with that key.
- By hand on 2026-10-06, against both versions: the security scan's verdict was `safe`, and `hermes fetchai-bridge probe-hermes` reported `importable`. On 2026-10-05, against `main` `bb236287`: installed from a `file://` URL with `--enable`; `UAGENT_SEED` from Hermes' `.env` reached the bridge; `serve` with `command` unset started Hermes' tools server; a remote signed client saw only `skills_list`, which returned real skills; `web_search` was denied by policy; and Ctrl-C shut everything down cleanly.
