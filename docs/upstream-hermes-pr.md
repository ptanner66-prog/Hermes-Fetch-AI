# Listing in Hermes: the plugin catalog

Hermes Fetch AI stays a standalone project. Its way into Hermes is one file in NousResearch/hermes-agent, `plugin-catalog/fetchai-bridge.yaml`, pinned to a commit of this repository. No Hermes code changes. Step-by-step instructions are in [`upstream/hermes-pr/SUBMIT.md`](../upstream/hermes-pr/SUBMIT.md); what was checked against Hermes' documentation, and how, is in [`validation.md`](validation.md).

## Where hermes-agent stands (checked 2026-10-06)

- **Releases.** The latest release is 0.21.5 (tag `v2026.9.24`, Python 3.11 to 3.13). `main` (`bb236287`) has since moved to Python 3.14. Both pin `mcp==2.0.0` in the `[mcp]` extra, and both only install from a checkout.
- **Placement.** `CONTRIBUTING.md` says third-party integrations ship as standalone plugins, listed through `plugin-catalog/`. `optional-skills/` is for official skills, and community skills belong on the Skills Hub.
- **Directory plugins.** `plugin.yaml` plus `__init__.py` with `register(ctx)`. Manifest v2 adds `python_runtime: external` (a sidecar: Hermes installs nothing) and `config_schema`, whose `secret` type is stored in Hermes' `.env`. `ctx.register_cli_command`, `ctx.register_skill`, `ctx.register_tool`, and `ctx.get_config`/`ctx.set_config` are public surfaces.
- **Catalog admission** (`plugin-catalog/README.md`, `website/docs/developer-guide/plugins/catalog-submission.md`; 0.21.5's catalog README had 9 rules, `main` has 16): one YAML entry pinned to a full 40-character SHA. Catalog CI runs `scripts/validate_plugin_catalog.py`, clones the repo at the pin, runs `hermes plugins validate --install-deps` on the `subdir` (manifest, loading, declared versus registered capabilities, config schema, dependencies, security scan, no core overrides), and checks for self-updaters. A maintainer then reviews the pinned tree against the rules and usually writes a `Disclosure —` sentence into the entry's `description`. The optional `known_issues` strings are shown at the install prompt.
- **Tools server.** `agent.transports.hermes_tools_mcp_server` serves flat arguments under mcp 2.0. The bridge's stdio field test passes against 0.21.5 and `main`.

## How the plugin meets the admission rules (`main`'s 16)

| Rule | How |
|------|-----|
| 1, one entry per PR | The PR adds only `plugin-catalog/fetchai-bridge.yaml`. |
| 2, a full SHA pin | Filled in at submission; with it, the entry passes `scripts/validate_plugin_catalog.py` (checked with the placeholder replaced). |
| 3, no self-updating code | None in the plugin. `hermes fetchai-bridge install`, which the user runs and confirms, installs the bridge version that matches the plugin, from this repository at the git tag `v<version>`; nothing updates on its own. The tag, not a SHA, is what pins the bridge; see "Open questions" below. |
| 4, a new pin is a new PR | Each release bumps `sha` and `version` together. |
| 5, the owner submits | From the `ptanner66-prog` account. |
| 6, capabilities match | `provides_tools` lists the four tools the plugin registers; no hooks, middleware, or required env vars. `hermes plugins validate` checks this. |
| 7, security scan | `hermes plugins validate --install-deps` passes on 0.21.5 and `main` in CI, with the security scan's verdict `safe` on both. |
| 8, Desktop plugins | Not applicable. |
| 9, no core overrides | Hermes surfaces: `register_cli_command`, `register_skill`, `register_tool` (with a `check_fn`), `get_config` and `set_config` (the plugin's own settings). It also calls three Hermes internals, never rebinding them: `tools.approval.is_approval_bypass_active` (reads whether YOLO is on), `tools.approval_prompt.request_elicitation_consent` (the payment prompt), and `hermes_cli.config.save_env_value`/`get_env_value` (keeps the plugin's own secrets during `setup`). The tools refuse if the first two are missing or change. |
| 10, dependencies | None installed into Hermes (`python_runtime: external`, standard library only). |
| 11, credentials | Only the plugin's own `config_schema` secrets, `UAGENT_SEED` and `AGENTVERSE_API_KEY`. The bridge gets an allowlisted environment, so model-provider keys in Hermes' `.env` never reach it. |
| 12, approvals and unattended runs | The tools are off until the user turns on `buyer_tools`. They refuse while YOLO mode is on, when Hermes cannot say whether it is, and in Hermes' plugin host (`plugins.isolation: host`). `fetchai_pay` asks through Hermes' confirmation prompt every time; it declines when nobody can answer. `install` and `setup` refuse without a terminal instead of waiting. `HERMES_YOLO_MODE` and `HERMES_NONINTERACTIVE` never reach the bridge or the tools server. Hermes' terminal can still run the bridge's `buyer pay` without the prompt, within the bridge's limits; the README says how to block it with `approvals.deny`. |
| 13, disclosure | The plugin README's "What this plugin does", the entry's `Disclosure —` sentence and `known_issues`, and the PR body below. |
| 14, truthful metadata | `requires_hermes: ">=0.21.5"`, the latest release, which CI tests; `version` matches `plugin.yaml`; `validate --install-deps` passes. |
| 15, no duplicates | There is no other Fetch.ai or uAgents entry. |
| 16, lineage | Original plugin, not a fork. |

## Open questions for review

- **The bridge's pin.** The catalog pins the plugin by SHA, and the plugin installs the bridge from the tag `v<version>`, which the repository owner could move. A commit SHA (a two-step release: the bridge's commit first, then the plugin commit that names it) or PyPI (whose versions cannot be replaced) would pin it as firmly as the catalog pins the plugin. Until then, the tag must exist and never move.
- **A public seam for "ask the user".** The plugin relies on two Hermes internals for the payment approval. Hermes' `CONTRIBUTING.md` asks for a feature request to widen the plugin surface instead; one is worth opening ("a plugin API to ask the user to confirm, shown even in YOLO mode, never remembered").

## Readiness

- [x] Directory plugin in [`hermes-plugin/fetchai-bridge`](../hermes-plugin/fetchai-bridge) ([`hermes-plugin.md`](hermes-plugin.md)).
- [x] CI, against Hermes 0.21.5 and a pinned `main`: `hermes plugins validate --install-deps` (`Validation passed`, security scan `safe`), `hermes plugins doctor --ci`, `hermes fetchai-bridge doctor` and `demo local`, the stdio field test, the guest Hermes field test, and the buying field test (YOLO detection, the prompt declining when nobody can answer, the `.env` writer).
- [x] Entry draft [`upstream/hermes-pr/plugin-catalog/fetchai-bridge.yaml`](../upstream/hermes-pr/plugin-catalog/fetchai-bridge.yaml). With a real SHA filled in it passes Hermes' `scripts/validate_plugin_catalog.py`; `tests/test_hermes_directory_plugin.py` keeps it consistent with `plugin.yaml`.
- [ ] Merge to `main` here, with CI green on the merge commit; bump the version and push its tag (`install` installs the bridge from it).
- [ ] Open the catalog PR ([`upstream/hermes-pr/SUBMIT.md`](../upstream/hermes-pr/SUBMIT.md)).

## Optional: Discussion first

Rule 5 lets the owner submit directly, so a Discussion is not required. A short one can still surface naming or scope concerns before review. Title:

```text
Fetch.ai agent economy as a catalog plugin (fetchai-bridge)
```

Body:

```text
hermes-fetch-ai (https://github.com/ptanner66-prog/Hermes-Fetch-AI, MIT) puts a Hermes on
Fetch.ai's agent network: it sells work the user chooses to other agents and ASI:One users,
and lets Hermes buy from other agents, on Fetch's testnet, with the user approving every
payment in Hermes' own confirmation prompt.

I'd like to list its plugin, fetchai-bridge, in plugin-catalog/. It is a stdlib-only
sidecar (python_runtime: external) with a `hermes fetchai-bridge` command, two skills, and
four buying tools that are off until the user turns them on and refuse in YOLO mode.

Questions:
1. The payment approval uses tools.approval_prompt.request_elicitation_consent, and the YOLO
   check tools.approval.is_approval_bypass_active. Would you take a public plugin API for
   "ask the user to confirm" instead?
2. Is agent.transports.hermes_tools_mcp_server a seam you are happy for external tools to
   depend on, or is there a more stable entry point?
3. Is the name fetchai-bridge fine for a community plugin not affiliated with Fetch.ai?
```

## Ready-to-paste catalog PR

Title: `feat(plugin-catalog): add fetchai-bridge`

Body (mirrors the hermes-agent PR template; replace `<sha>`, `<version>`, and `<platform>`):

```markdown
## What does this PR do?

Adds a catalog entry for `fetchai-bridge`, the Hermes plugin for
[Hermes Fetch AI](https://github.com/ptanner66-prog/Hermes-Fetch-AI) (MIT). It puts Hermes
on Fetch.ai's agent network: it sells work the user chooses (research by a throwaway guest
Hermes, a defensive code review by a local model, or the user's own program) to other agents
and ASI:One users, and lets Hermes buy from other agents. Testnet only; the user approves
every payment Hermes' tools make. One file, no Hermes code changes.

Hermes surfaces used: `ctx.register_cli_command` (`hermes fetchai-bridge`),
`ctx.register_skill` (`operate`, `buy`), `ctx.register_tool` with a `check_fn`
(`fetchai_find_agents`, `fetchai_message_agent`, `fetchai_read_replies`, `fetchai_pay`, in a
`fetchai` toolset, unavailable until the `buyer_tools` setting is on), `ctx.get_config` and
`ctx.set_config` (its own settings only), and a manifest v2 `config_schema` (`buyer_tools`,
`config`, `command`, and the secrets `uagent_seed` and `agentverse_api_key`, stored as
`UAGENT_SEED` and `AGENTVERSE_API_KEY`). It also calls three Hermes internals, never
rebinding them: `tools.approval.is_approval_bypass_active`,
`tools.approval_prompt.request_elicitation_consent`, and
`hermes_cli.config.save_env_value`/`get_env_value`. `python_runtime: external`: the plugin is
stdlib-only; the bridge pins its own dependencies (uAgents, mcp 1.28.1) in a separate
environment.

Disclosures (rule 13; the plugin README has the full list):
- Processes: runs the separately installed `hermes-fetch-ai` executable, without a shell,
  when the user runs `hermes fetchai-bridge ...` and, with `buyer_tools` on, when Hermes
  uses a buying tool. `install`, run and confirmed by the user, runs `uv tool install` (or
  `pipx install`) of the bridge from GitHub at the git tag of the plugin's version; nothing
  updates itself.
- Writes to Hermes: only during `setup`, run by the user: the plugin's own secrets
  `UAGENT_SEED` (a new random key, only when there is none) and `AGENTVERSE_API_KEY` (only
  if pasted), with Hermes' `.env` writer, and, if the user agrees, the plugin's own
  `buyer_tools` setting. No other Hermes setting.
- Environment and credentials: the bridge gets an allowlisted environment (`UAGENT_SEED`,
  `AGENTVERSE_API_KEY`, `HERMES_HOME`, `PATH`, `HOME`, locale, temp, proxy and certificate
  settings, the Windows essentials, and Hermes' interpreter path). Model-provider keys and
  other `.env` entries are not passed.
- Background listener: `start` runs the bridge (`serve`) in the background until `stop`, with
  a private log; it listens on the configured port on all interfaces (the README says to
  firewall it). When configured to share Hermes tools, it starts Hermes' tools MCP server as
  a child with a short environment allowlist.
- Selling (off unless set up): each paid request runs the user's configured program (no
  shell, empty folder, timeout) or a throwaway guest Hermes with only web search and its own
  keys file; payments are verified on Fetch's testnet ledger. Research uses the user's own
  model key, which costs real money; setup caps it at 20 requests a day by default.
- Buying (off until `buyer_tools`): the tools search Agentverse, send the model's messages to
  the agents it names through the running bridge, and pay test FET from the bridge's buying
  wallet only after the user accepts Hermes' confirmation prompt; the bridge caps each
  payment, each seller, and each day. The tools refuse in YOLO mode, when Hermes cannot say,
  and in the plugin host. Hermes' terminal can run the bridge's `buyer pay` without the
  prompt, within the same caps; the README shows the `approvals.deny` rule that blocks it.
- Network: Fetch's testnet ledger (payments, balances, `status`), Agentverse (search,
  mailbox, listing, which the user runs or confirms), the testnet faucet when the user asks,
  and, for a guest Hermes, the user's model provider and web search. No telemetry.
- Funds: testnet only; mainnet is locked. Almanac contract registration is off unless
  configured.

## Related Issue

None; catalog entry.

## Type of Change

- [x] ✨ New feature (non-breaking change that adds functionality)

## Changes Made

- `plugin-catalog/fetchai-bridge.yaml`: pinned to `<sha>` (`version: "<version>"`,
  `subdir: hermes-plugin/fetchai-bridge`, `requires_hermes: ">=0.21.5"`, `category: tools`,
  `provides_tools` for the four tools, `known_issues`).

## How to Test

1. `python3 scripts/validate_plugin_catalog.py plugin-catalog/fetchai-bridge.yaml`
2. At the pinned commit, `hermes plugins validate <clone>/hermes-plugin/fetchai-bridge --install-deps`;
   expect `Validation passed.` with security scan `safe`.
3. `hermes plugins install fetchai-bridge`, `hermes plugins enable fetchai-bridge`,
   `hermes fetchai-bridge install`, then `hermes fetchai-bridge demo chat` and `demo buy`
   (offline, simulated ledger).

The plugin's own CI runs `hermes plugins validate --install-deps`, `hermes plugins doctor --ci`,
the plugin's CLI, and field tests against real Hermes (tools server, guest Hermes, the buying
guards) on Hermes 0.21.5 and a pinned `main`, plus opt-in live tests on Fetch's testnet.

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
- [x] Tool descriptions/schemas: the four tools' schemas are in the plugin; their errors are
      returned as JSON, never raised
```

## What not to propose

- an in-tree bridge adapter or changes to Hermes core;
- new default model tools or toolsets;
- new Hermes-side environment variables;
- bridging `hermes mcp serve` (conversations/messaging);
- claims that the plugin works on Hermes releases CI does not test.
