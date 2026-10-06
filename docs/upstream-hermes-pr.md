# Listing in Hermes: the plugin catalog

Hermes Fetch AI stays a standalone project. Its way into Hermes is one file in NousResearch/hermes-agent, `plugin-catalog/fetchai-bridge.yaml`, pinned to a commit of this repository. No Hermes code changes. Step-by-step instructions are in [`upstream/hermes-pr/SUBMIT.md`](../upstream/hermes-pr/SUBMIT.md).

## Where hermes-agent stands (checked 2026-10-06)

- **Releases.** The latest release is 0.21.5 (tag `v2026.9.24`, Python 3.11 to 3.13). `main` (`bb236287`) has since moved to Python 3.14. Both pin `mcp==2.0.0` in the `[mcp]` extra, and both only install from a checkout.
- **Placement.** `CONTRIBUTING.md` says third-party integrations ship as standalone plugins, listed through `plugin-catalog/`. `optional-skills/` is for official skills, and community skills belong on the Skills Hub.
- **Directory plugins.** `plugin.yaml` plus `__init__.py` with `register(ctx)`. Manifest v2 adds `python_runtime: external` (a sidecar: Hermes installs nothing) and `config_schema`, whose `secret` type is stored in Hermes' `.env`. `ctx.register_cli_command` and `ctx.register_skill` are public surfaces.
- **Catalog admission** (`plugin-catalog/README.md`, `website/docs/developer-guide/plugins/catalog-submission.md`): one YAML entry pinned to a full 40-character SHA. Catalog CI runs `scripts/validate_plugin_catalog.py`, clones the repo at the pin, runs `hermes plugins validate --install-deps` on the `subdir` (manifest, loading, declared versus registered capabilities, config schema, dependencies, security scan, no core overrides), and checks for self-updaters. Then a maintainer reviews the pinned tree against the 16 admission rules and usually writes a `Disclosure —` sentence into the entry's `description`.
- **Tools server.** `agent.transports.hermes_tools_mcp_server` serves flat arguments under mcp 2.0. The bridge's stdio field test passes against 0.21.5 and `main`.

## How the plugin meets the rules that matter here

| Rule | How |
|------|-----|
| 3, no self-updating code | None. Updates arrive only through a new pin. |
| 5, owner submits | Submit from the `ptanner66-prog` account. |
| 6, capabilities match | No tools, hooks, middleware, or required env vars; the entry's `capabilities` lists are empty. `hermes plugins validate` checks this. |
| 9, no core overrides | Only `register_cli_command`, `register_skill`, and `get_config`. |
| 10, dependencies | None installed into Hermes (`python_runtime: external`, stdlib-only). |
| 11, credentials | Only `UAGENT_SEED`, the plugin's own `config_schema` secret. The bridge gets an allowlisted environment, so model-provider keys in Hermes' `.env` never reach it. |
| 12, approvals and unattended runs | No tools, so the agent reaches the bridge only through the terminal tool under normal approvals. The bridge and the tools server get allowlisted environments, so `HERMES_YOLO_MODE` and `HERMES_NONINTERACTIVE` never reach them. Nothing prompts or waits for input. |
| 13, disclosure | Plugin README "What this plugin does" (processes, environment, listener, what remote agents see, network, funds, files), the PR body below, and a `Disclosure —` sentence already in the draft entry. |
| 14, truthful metadata | `requires_hermes: ">=0.21.5"`, the latest release, which CI tests; `version` matches `plugin.yaml`; `validate --install-deps` passes. |
| 16, lineage | Original plugin, not a fork. |

## Readiness

- [x] Directory plugin in [`hermes-plugin/fetchai-bridge`](../hermes-plugin/fetchai-bridge) ([`hermes-plugin.md`](hermes-plugin.md)).
- [x] CI, against Hermes 0.21.5 and a pinned `main`: `hermes plugins validate --install-deps` (`Validation passed`; the security scan's verdict, checked by hand on 2026-10-06, was `safe`), `hermes plugins doctor --ci`, `hermes fetchai-bridge doctor` and `demo local`, and the stdio field test.
- [x] Entry draft [`upstream/hermes-pr/plugin-catalog/fetchai-bridge.yaml`](../upstream/hermes-pr/plugin-catalog/fetchai-bridge.yaml). With a real SHA filled in it passes Hermes' `scripts/validate_plugin_catalog.py` and loads with Hermes' catalog loader; `tests/test_hermes_directory_plugin.py` keeps it consistent with `plugin.yaml`.
- [ ] Merge the plugin to `main` here, with CI green on the merge commit.
- [ ] Optionally tag `v1.0.0` (the pin is still the commit SHA).
- [ ] Open the catalog PR ([`upstream/hermes-pr/SUBMIT.md`](../upstream/hermes-pr/SUBMIT.md)).

## Optional: Discussion first

Rule 5 lets the owner submit directly, so a Discussion is not required. A short one can still surface naming or scope concerns before review. Title:

```text
Fetch.ai uAgents bridge as a catalog plugin (fetchai-bridge)
```

Body:

```text
hermes-fetch-ai (https://github.com/ptanner66-prog/Hermes-Fetch-AI, MIT) lets Fetch.ai
uAgents call a default-deny, allowlisted subset of Hermes tools. Hermes stays the local
execution layer; uAgents supplies identity, signed envelopes, and addressing.

I'd like to list its plugin, fetchai-bridge, in plugin-catalog/. It is a stdlib-only
sidecar (python_runtime: external): it adds `hermes fetchai-bridge`, which runs the
separately installed bridge, and ships an operate skill. No tools, hooks, or middleware.

The bridge runs `python -m agent.transports.hermes_tools_mcp_server` with Hermes' own
interpreter as a stdio child (shell=False, env allowlist, timeouts), never touches
`hermes mcp serve`, and exposes only skills_list by default.

Questions:
1. Is agent.transports.hermes_tools_mcp_server a seam you are happy for external tools
   to depend on, or is there a more stable entry point?
2. Is the name fetchai-bridge fine for a community plugin not affiliated with Fetch.ai?
```

## Ready-to-paste catalog PR

Title: `feat(plugin-catalog): add fetchai-bridge`

Body (mirrors the hermes-agent PR template; replace `<sha>` and `<platform>`):

```markdown
## What does this PR do?

Adds a catalog entry for `fetchai-bridge`, the Hermes plugin for
[Hermes Fetch AI](https://github.com/ptanner66-prog/Hermes-Fetch-AI) (MIT), a small bridge
that lets Fetch.ai uAgents call a default-deny, allowlisted subset of Hermes tools. The
plugin adds `hermes fetchai-bridge`, which runs the separately installed bridge, and ships
an `operate` skill. One file, no Hermes code changes.

Hermes surfaces used: `ctx.register_cli_command`, `ctx.register_skill`, `ctx.get_config`,
and a manifest v2 `config_schema` (`command`, plus `uagent_seed` as a `secret` stored as
`UAGENT_SEED`). No tools, hooks, or middleware, so `capabilities` is empty.
`python_runtime: external`: the plugin is stdlib-only and installs nothing into Hermes'
environment; the bridge pins its own dependencies (uAgents, mcp 1.28.1) in a separate one.

Disclosures (rule 13):
- Processes: runs one subprocess, without a shell, only when the user runs
  `hermes fetchai-bridge ...`: the separately installed `hermes-fetch-ai` executable.
  `probe-hermes` also runs Hermes' interpreter once to check an import.
- Environment and credentials: the bridge gets an allowlisted environment: `UAGENT_SEED`
  (the plugin's own `config_schema` secret, from `$HERMES_HOME/.env`), `HERMES_HOME`,
  `PATH`, `HOME`, locale, temp-directory, proxy and certificate settings, and the Windows
  essentials, plus Hermes' interpreter path and `PYTHONPATH` as
  `HERMES_FETCH_AI_HERMES_PYTHON` and `HERMES_FETCH_AI_HERMES_PYTHONPATH`. Model-provider
  API keys and other `.env` entries are not passed.
- Long-running listener: `hermes fetchai-bridge serve` runs until stopped and listens on the
  configured port on all network interfaces (there is no bind-address setting; the README
  says to firewall the port). It starts `python -m agent.transports.hermes_tools_mcp_server`
  with Hermes' interpreter as a child process with a shorter allowlist (`PATH`, `HOME`,
  `TMPDIR`, `HERMES_HOME`, locale).
- What remote agents reach: in the example config, only `skills_list`, which returns the
  name, description, and category of every installed skill (the README says to remove it
  if that is sensitive). Every other tool is denylisted until the user changes the policy,
  and the tools server never serves terminal, file, or process tools. Calls need replay
  metadata and pass rate limits, URL (private-address) and shell-character checks, and size
  caps; every decision goes to a redacted JSONL audit log.
- Network: with `publish_manifest: false`, as in the example config, the bridge makes no
  outbound calls of its own; replying to a remote agent can look up that agent's endpoint
  in the Almanac (Agentverse's API, falling back to the Fetch ledger). With
  `publish_manifest: true` or mailbox mode, it also registers with the Almanac and
  Agentverse.
- Funds: with `publish_manifest: true`, uAgents registers the bridge on the Almanac
  contract, which can pay registration fees from the wallet derived from `UAGENT_SEED`.
  Nothing is spent with `publish_manifest: false`.
- Files: `serve` writes a JSONL audit log, without arguments or outputs, under
  `~/.local/state/hermes-fetch-ai/` by default.
- Approvals (rule 12): no tools, so the agent reaches the bridge only through the terminal
  tool under normal approvals; `HERMES_YOLO_MODE` and `HERMES_NONINTERACTIVE` reach neither
  the bridge nor the tools server; nothing prompts or waits for input.
- No telemetry, no self-updates, and the plugin itself makes no network calls.
- Community project, not affiliated with Fetch.ai.

## Related Issue

None; catalog entry.

## Type of Change

- [x] ✨ New feature (non-breaking change that adds functionality)

## Changes Made

- `plugin-catalog/fetchai-bridge.yaml`: pinned to `<sha>` (`version: "1.0.0"`,
  `subdir: hermes-plugin/fetchai-bridge`, `requires_hermes: ">=0.21.5"`,
  `category: tools`, empty `capabilities`).

## How to Test

1. `python3 scripts/validate_plugin_catalog.py plugin-catalog/fetchai-bridge.yaml`
2. At the pinned commit, `hermes plugins validate <clone>/hermes-plugin/fetchai-bridge --install-deps`;
   expect `Validation passed.` with security scan `safe`.
3. `uv tool install --python 3.12 "hermes-fetch-ai @ git+https://github.com/ptanner66-prog/Hermes-Fetch-AI@<sha>"`,
   then `hermes plugins install fetchai-bridge`, `hermes plugins enable fetchai-bridge`,
   and `hermes fetchai-bridge demo local`; expect `echo result: hello`.

The plugin's own CI runs `hermes plugins validate --install-deps`, `hermes plugins doctor --ci`,
`hermes fetchai-bridge doctor` and `demo local`, and a stdio field test against real Hermes
tools, on Hermes 0.21.5 and a pinned `main`.

## Checklist

### Code

- [x] I've read the Contributing Guide and the catalog submission guide
- [x] My commit messages follow Conventional Commits
- [x] I searched for existing PRs; there is no Fetch.ai/uAgents entry
- [x] My PR contains only this catalog entry
- [ ] I've run `pytest tests/ -q`: N/A, YAML-only change; catalog CI validates the entry
- [ ] `python scripts/check` passes: N/A, YAML-only change
- [ ] I've added tests: N/A, the plugin is tested in its own repository
- [x] I've tested on my platform: <platform>

### Documentation & Housekeeping

- [x] Documentation: N/A in hermes-agent; the plugin README renders on its catalog page
- [x] `cli-config.yaml.example`: N/A
- [x] `CONTRIBUTING.md` / `AGENTS.md`: N/A
- [x] Cross-platform: the plugin uses `shutil.which` and `subprocess` without a shell; the
      bridge's CI covers Linux, macOS, and Windows
- [x] Tool descriptions/schemas: N/A, no tools
```

## What not to propose

- an in-tree bridge adapter or changes to Hermes core;
- new default model tools or toolsets;
- new Hermes-side environment variables;
- bridging `hermes mcp serve` (conversations/messaging);
- claims that the plugin works on Hermes releases CI does not test.
