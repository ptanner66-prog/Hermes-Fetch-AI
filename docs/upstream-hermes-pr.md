# Upstream Contribution Plan: NousResearch/hermes-agent

Hermes Fetch AI should remain a standalone plugin package unless Hermes maintainers explicitly request a larger footprint. This document is a maintainer-facing plan, not a claim that Hermes core already enables every plugin command out of the box.

## Where hermes-agent stands (checked 2026-10-05, `main` at `bb236287`)

- **Placement rules.** `CONTRIBUTING.md` says third-party product integrations "do not land in this repo" and ship as standalone plugins, listed through `plugin-catalog/`. Niche or community skills belong on the Skills Hub; `optional-skills/` is for official skills that are useful but not universally needed.
- **Runtime.** Hermes now develops on Python 3.14 (`.python-version`; `[tool.uv] environments = ["python_version >= '3.14'"]`) and its `[mcp]` extra pins `mcp==2.0.0`. This package requires Python `<3.13` and pins `mcp==1.28.1` through uAgents, so it cannot be installed into a current Hermes environment. Run it from its own environment and point `hermes_mcp.command` at Hermes' Python (stdio mode).
- **Tools server.** `agent/transports/hermes_tools_mcp_server.py` still exists with `_build_server()` and a `__main__` entry, but now builds flat tool signatures from each tool's JSON schema. The `kwargs` wrapper that v0.16.x needed is gone, and the in-process mode cannot import the mcp 2.0 server under mcp 1.x.
- **Plugins.** The `hermes_agent.plugins` entry-point group and `ctx.register_cli_command(name, help, setup_fn, handler_fn, description)` are unchanged. Third-party plugins are opt-in (`hermes plugins enable <name>`, config key `plugins.enabled`). `ctx.register_skill(name, path)` lets a plugin ship its own skill, so a plugin can carry `fetchai-bridge` without any hermes-agent skill PR.
- **Catalog admission** (`plugin-catalog/README.md`, `website/docs/developer-guide/plugins/catalog-submission.md`): one YAML entry pinned to a full 40-character commit SHA; the pinned tree must contain a `plugin.yaml` manifest and an `__init__.py` entrypoint; `hermes plugins validate --install-deps` must pass; `requires_hermes` is a truthful SemVer floor; network calls, stored credentials, and background processes are disclosed in the PR and the plugin README.

## Recommended path

1. **Open a GitHub Discussion** (Hermes routes design proposals there) using the draft below. Ask whether maintainers want a catalog entry for a Fetch.ai uAgents bridge.
2. **Meanwhile, publish the skill on the Skills Hub** (a skills registry plus a post in the Nous Research Discord). No hermes-agent PR is needed for that.
3. **Make the repo catalog-ready**, then open a `plugin-catalog/<name>.yaml` PR:
   - Add a thin directory plugin (`plugin.yaml` + `__init__.py`) whose `register(ctx)` adds `hermes fetchai ...` by shelling out to the separately installed `hermes-fetch-ai` executable, and calls `ctx.register_skill("fetchai-bridge", ...)`. That keeps the bridge's uAgents/mcp 1.x dependencies out of Hermes' environment.
   - Prove the stdio path against a current Hermes (`tests/test_field_hermes_stdio.py`, see `docs/demo.md`).
   - Write the README disclosures: the bridge listens on a port and talks to the Fetch network/Agentverse when configured to; it reads `UAGENT_SEED`; `serve` is a long-running process.
4. **Only if a maintainer asks for it in-tree**, use the `optional-skills/` route in `upstream/hermes-pr/SUBMIT.md`.

Do **not** propose vendoring bridge code into Hermes core.

## Current verified surface in this repo

- Package CLI: `hermes-fetch-ai doctor|probe-hermes|serve|demo`.
- Plugin entry point: `fetchai = "hermes_fetch_ai.hermes_plugin"`; once installed in Hermes' environment and enabled with `hermes plugins enable fetchai`, it exposes `hermes fetchai doctor|probe|serve|demo`.
- Skill payload: `upstream/hermes-pr/optional-skills/autonomous-ai-agents/fetchai-bridge/SKILL.md` (frontmatter matches the current authoring rules, including `platforms`).

## Draft Discussion post

Title:

```text
Fetch.ai uAgents bridge: catalog plugin for exposing allowlisted Hermes tools to uAgents
```

Body:

```text
hermes-fetch-ai (https://github.com/ptanner66-prog/Hermes-Fetch-AI, MIT) is a
standalone package that lets Fetch.ai uAgents call a default-deny, allowlisted subset
of Hermes tools. Hermes stays the local execution layer; uAgents supplies identity,
signed envelopes, and addressing.

How it uses Hermes:
- runs `python -m agent.transports.hermes_tools_mcp_server` from the Hermes
  environment as a stdio subprocess (shell=False, env allowlist, timeouts);
- never touches `hermes mcp serve` (conversations/messaging/approvals);
- only `skills_list` is public by default; everything else is denylisted;
- replay protection, rate limits, argument validation (URL/SSRF and shell guards),
  bounded output, and a redacted audit log on every call.

Questions:
1. Would a plugin-catalog entry be welcome? The plan is a thin plugin that adds
   `hermes fetchai ...` and ships a skill via register_skill, while the bridge runs
   in its own environment.
2. Is agent.transports.hermes_tools_mcp_server a seam you are happy for external
   tools to depend on, or is there a more stable entry point?
3. Anything you would want disclosed or restricted beyond the catalog rules?
```

## Ready-to-paste PR body

For the `optional-skills/` route; it mirrors the hermes-agent PR template.

```markdown
## What does this PR do?

Adds an optional `fetchai-bridge` skill that teaches Hermes to operate
[hermes-fetch-ai](https://github.com/ptanner66-prog/Hermes-Fetch-AI), a standalone
MIT package that exposes a default-deny, allowlisted subset of Hermes tools to
Fetch.ai uAgents. No Hermes core files change.

## Related Issue

Discussion: #<number>

## Type of Change

- [x] 🎯 New skill (bundled or hub)

## Changes Made

- `optional-skills/autonomous-ai-agents/fetchai-bridge/SKILL.md`
- Generated docs from `website/scripts/generate-skill-docs.py` (catalog row, skill page, sidebar entry)

## How to Test

1. `scripts/run_tests.sh tests/skills/`
2. `hermes --toolsets skills -q "Use the fetchai-bridge skill to run the local demo"`;
   expect `echo result: hello` from `hermes-fetch-ai demo local`.

## Checklist

- [x] I've read the Contributing Guide
- [x] Commit messages follow Conventional Commits
- [x] I searched existing PRs; there is no Fetch.ai/uAgents integration in the repo
- [x] The PR contains only this skill and its generated docs
- [x] `pytest tests/ -q` and `python scripts/check` pass
- [x] Tested on: <platform>

## For New Skills

- [ ] Broadly useful to most users: no, which is why it is optional, not bundled
- [x] SKILL.md follows the standard format
- [ ] No external dependencies: it requires the separately installed
      `hermes-fetch-ai` command (installed with `uv tool install`, not into Hermes' environment)
- [x] Tested end to end with `hermes --toolsets skills -q`

Security model: default-deny tool policy, replay protection, rate limits, URL/shell
argument guards, bounded output, redacted audit; the seed comes only from the
`UAGENT_SEED` environment variable; the Hermes conversations/messaging surface is
never bridged.
```

## What not to propose

- in-tree bridge adapter directory;
- changes to core agent runtime;
- new default model tools/toolsets;
- new `HERMES_*` env vars;
- bridging `hermes mcp serve` conversations/messaging;
- public claims that pip install alone guarantees `hermes fetchai ...` on all Hermes versions.
