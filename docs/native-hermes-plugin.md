# Native Hermes Plugin Path

Hermes Fetch AI is designed to be a small standalone Hermes plugin, not a Hermes core fork.

## Current integration shape

This package exposes a Hermes plugin entry point:

```toml
[project.entry-points."hermes_agent.plugins"]
fetchai = "hermes_fetch_ai.hermes_plugin"
```

That entry point makes the package discoverable to Hermes plugin loading when the package is installed in Hermes' own environment. Current Hermes (checked at `main` `bb236287`, 2026-10-05) loads third-party plugins only after `hermes plugins enable fetchai` (config key `plugins.enabled`), and its `register_cli_command(name, help, setup_fn, handler_fn, description)` signature matches what this plugin calls.

**Current blocker:** hermes-agent now develops on Python 3.14 and pins `mcp==2.0.0` in its `[mcp]` extra, while this package supports Python 3.11/3.12 and pins `mcp==1.28.1` through uAgents. The two cannot share one environment today, so `hermes fetchai ...` is not reachable on a current Hermes install. The standalone CLI in its own environment is the supported path.

Verified package CLI:

```bash
hermes-fetch-ai doctor
hermes-fetch-ai probe-hermes
hermes-fetch-ai demo local
hermes-fetch-ai serve --config /absolute/path/to/examples/hermes-stdio.yaml
```

Once the package is installed in Hermes' environment and enabled, the plugin delegates to:

```bash
hermes fetchai doctor
hermes fetchai probe
hermes fetchai demo local
hermes fetchai serve --config /absolute/path/to/examples/hermes-stdio.yaml
```

The plugin delegates to the package CLI and does not patch Hermes core modules.

## Why this is the Teknium-ready shape

This follows the Hermes footprint ladder:

1. no core runtime changes;
2. no new default tool schema cost for every Hermes session;
3. no new network surface enabled by default;
4. opt-in plugin install, explicit enablement, and explicit `serve` command;
5. Hermes remains local execution, Fetch/uAgents remains network/addressing.

The intended Hermes-backed backend is the Hermes tools MCP server as a stdio subprocess:

```text
python -m agent.transports.hermes_tools_mcp_server
```

That module is version-dependent and may not exist in all Hermes installs. Until Hermes maintainers bless a stable tools-server module, treat the Hermes-backed path as gated field integration and keep the fake/local demo as the default CI proof. The conversations/messaging MCP server is excluded by design.

## Setup flow for Hermes maintainers

Hermes now has a curated plugin catalog (`plugin-catalog/<name>.yaml`, installed with `hermes plugins install <name>`). Catalog entries pin a full commit SHA, and the pinned tree must contain a `plugin.yaml` manifest plus an `__init__.py` entrypoint, so this repo needs a thin directory plugin before it can be listed. See [`upstream-hermes-pr.md`](upstream-hermes-pr.md) for the plan.

If Hermes wants this to appear in setup UX without vendoring the bridge into core, the smallest acceptable change is a setup/catalog entry that installs and enables this plugin package.

Proposed user-facing flow after Hermes-side enablement support exists:

```bash
hermes setup
# Optional integrations -> Fetch.ai uAgents bridge -> install + enable hermes-fetch-ai
hermes fetchai doctor
hermes fetchai demo local
```

Implementation options, in order of least core impact:

1. docs/catalog listing only;
2. optional skill that teaches Hermes how to run `hermes-fetch-ai`;
3. setup menu entry that installs the package into the active Hermes environment and adds `fetchai` to the enabled plugin config;
4. plugin CLI wiring smoke in Hermes core for entry-point plugins;
5. only if maintainers request it, a tiny in-repo integration page.

Do not vendor this bridge into Hermes core unless maintainers explicitly ask for that larger footprint.

## Verification evidence for plugin readiness

The release gate for package/plugin readiness is:

```bash
uv run python -m hermes_fetch_ai.cli doctor
uv run python -m hermes_fetch_ai.cli doctor --contamination-scan
uv run ruff check .
uv run mypy src tests
uv run pytest -q
uv run python -m hermes_fetch_ai.cli demo local
rm -rf dist build
uv run python -m build
uv run python -m twine check dist/*
```

A wheel smoke must also install the built wheel into a fresh virtual environment and confirm:

- `hermes-fetch-ai doctor` exits 0;
- the `hermes_agent.plugins` entry point contains `fetchai`;
- importing `hermes_fetch_ai.hermes_plugin` succeeds.

A separate Hermes-native smoke should be added once the plugin can be installed into a current Hermes environment (Hermes already supports enablement and CLI wiring):

- install Hermes in an isolated environment;
- install the built bridge wheel;
- enable `fetchai` through the supported Hermes plugin mechanism;
- run `hermes fetchai --help`, `hermes fetchai doctor`, and `hermes fetchai demo local`.

## Maintainer-facing boundaries

- No secrets in config examples.
- Production seed only via `UAGENT_SEED`.
- Replay metadata required for `CallTool` by default.
- `skills_list` is the only Hermes-backed demo-public tool.
- `skill_view`, `terminal`, browser, filesystem, messaging, approval, and conversations surfaces stay private unless an operator explicitly allowlists them for a known sender.
