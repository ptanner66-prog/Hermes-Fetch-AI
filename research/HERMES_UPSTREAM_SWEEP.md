# Hermes Upstream Sweep

Updated: 2026-05-17T03:35:34Z

Scope: public `NousResearch/hermes-agent` and local source-checkout seams relevant to a narrow Fetch/uAgents bridge. No upstream files were modified in this run.

## Repository state observed

Public GitHub API:

- Repository: `NousResearch/hermes-agent`
- Default branch: `main`
- Observed head: `3b39096904ae`
- Observed commit date: 2026-05-17T00:18:25Z

Local checkout:

- Path: `C:\Users\ptann\OneDrive\Work\hermes-agent-main`
- Branch: `main`
- State: behind `origin/main` by 1 and dirty.
- Disposition: reference-only for this run. No branch, commit, or PR was created against the Hermes checkout.

## Source files checked

Public raw source / local reference:

- `mcp_serve.py`
- `tests/test_mcp_serve.py`
- `hermes_cli/main.py`
- `hermes_cli/plugins.py`
- `hermes_cli/plugins_cmd.py`
- `hermes_cli/config.py`

## Findings

### Hermes already exposes the correct seam: `hermes mcp serve`

`hermes_cli/main.py` defines an `mcp` command group and a `serve` subcommand described as running Hermes as an MCP server. `mcp_serve.py` exposes conversation/message/event/permission tools over stdio MCP.

Verified locally through this repo:

- `doctor --config examples\hermes-stdio-env.yaml --probe-backend` reported `backend: ok: 10 tools`.
- `demo hermes --config examples\hermes-stdio-env.yaml` called `conversations_list` through the bridge and returned `{"count": 0, "conversations": []}` when no sessions were present.

Bridge implication: do not reach into Hermes internals for tool dispatch when stdio MCP is enough. The bridge should wrap `hermes mcp serve` and keep the Hermes process local.

### Hermes MCP server includes side-effecting tools, so bridge policy is mandatory

The MCP server includes both read/poll style tools and side-effecting send/approval tools. This repo's `examples/hermes-stdio-env.yaml` exposes only:

- `conversations_list`
- `events_poll`

and denies:

- `messages_send`
- `permissions_respond`

Bridge implication: uAgent identity and MCP tool listing are not authorization. The bridge's default-deny and denylist precedence are required safety boundaries.

### Hermes tests already exercise the MCP server shape

`tests/test_mcp_serve.py` verifies the MCP module functions and fake FastMCP path. That makes a future upstream PR easier: it can add a small bridge/plugin test suite without replacing the existing MCP server tests.

Bridge implication: PR one should add tests around optional uAgents bridge loading, policy-filtered tool exposure, and stdio command construction, not retest all Hermes MCP behavior.

### Hermes plugin system can host the integration without core churn

`hermes_cli/plugins.py` defines `PluginContext` and exposes registration hooks including `register_tool()` and `register_cli_command(...)`. Plugins are opt-in through config allowlists and can be distributed separately.

Bridge implication: first upstream shape should be plugin/CLI-command-first:

- default disabled;
- optional dependencies;
- no import-time failure if uAgents packages are absent;
- no changes to the core agent loop;
- no changes to Hermes' default tools or prompts.

### Config/profile conventions matter

Hermes config code has established home/config/env handling and plugin enable/disable conventions. A future PR should use Hermes helpers and profile-aware paths rather than hardcoded user paths.

Bridge implication: this standalone proof's local path examples should become environment/config entries in upstream. Machine-specific examples belong in docs only.

## Recommended upstream PR shape

Title shape:

`feat(plugins): add optional Fetch uAgents bridge for Hermes MCP tools`

Minimal contents:

- bundled or external plugin skeleton;
- CLI command such as `hermes uagents serve` or plugin command equivalent;
- optional dependency check for `uagents`, `uagents-core`, and `uagents-adapter[mcp]`;
- config schema/defaults with bridge disabled by default;
- safe sample policy exposing no tools or one read-only demo tool;
- docs page explaining Fetch/uAgents identity, mailbox, Almanac/manifest, and payment dry-run boundaries;
- tests for missing dependency, default-off config, policy filtering, and no secret-shaped config values.

Do not include in PR one unless maintainers ask:

- A2A adapter work;
- wallet custody or settlement;
- hosted Agentverse account automation;
- gateway platform adapter work;
- broad marketplace UX;
- changes to Hermes prompt/tool defaults.

## Current local proof evidence for upstream conversation

- Local fake bridge demo: exit 0, `echo result: hello`.
- Real Hermes stdio probe: exit 0, `backend: ok: 10 tools`.
- Real Hermes stdio bridge call: exit 0, `conversations_list` returned empty session list through the bridge.
- Test suite: `77 passed in 17.94s`.
- Ruff/mypy/contamination: green.
- Payment dry-run: exit 0, `CompletePayment`, no settlement.
- Mailbox missing-seed blocker: enforced and documented.

## Remaining upstream blockers

- Maintainer direction on whether the bridge should live as bundled plugin, external plugin, or small CLI integration.
- Hosted Agentverse/mailbox transcript evidence after operator setup.
- Decision on whether payment dry-run belongs in PR one or in a follow-up doc/test only.
