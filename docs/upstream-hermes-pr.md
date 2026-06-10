# Upstream Contribution Plan: NousResearch/hermes-agent

Verified against `hermes-agent` main on 2026-06-10 (v0.16.0 era). Sources:
`CONTRIBUTING.md`, `.github/PULL_REQUEST_TEMPLATE.md`, `AGENTS.md`
("Contribution Rubric — What We Want / What We Don't", "The Footprint Ladder",
"Plugins"), and recently merged PR titles.

## The shape the maintainers accept

Hermes maintainer conventions that decide our shape:

- Conventional Commits titles: `type(scope): description` (`fix(cli): ...`,
  `feat(skills): ...`, `docs(agents): ...`). Confirmed across recent merged PRs.
- Footprint Ladder: prefer, in order, extend existing -> CLI command + skill ->
  service-gated tool -> plugin -> MCP catalog -> new core tool (last resort).
- Plugin policy (May 2026): plugins MUST NOT modify core files; new
  integration categories ship as standalone plugin repos discovered from
  `~/.hermes/plugins/` or the `hermes_agent.plugins` pip entry-point group, with
  CLI subcommands registered through `ctx.register_cli_command(...)`.
- "Expansive at the edges, conservative at the waist": new reach is welcome,
  but core agent + model tool schema additions are paid for on every API call.
- No new `HERMES_*` env vars for non-secret config; `.env` is secrets only.
- Tests: hermetic (`scripts/run_tests.sh`), stdlib + pytest + mock, no live
  network, `monkeypatch`/`tmp_path`; behavior contracts, not change detectors.
- Author credit: the human contributor is credited first, not the tool.

Conclusion: this integration is **Footprint Ladder rung 4 — a standalone
plugin** — and that is already implemented in this repo:

- `src/hermes_fetch_ai/hermes_plugin.py` exposes `register(ctx)`.
- `pyproject.toml` declares the `hermes_agent.plugins` entry point `fetchai`.
- Installing `hermes-fetch-ai` into a Hermes environment yields
  `hermes fetchai doctor|probe|serve|demo` with zero Hermes core changes.
- The bridge consumes Hermes through the existing
  `agent.transports.hermes_tools_mcp_server` stdio surface; nothing in the
  Hermes tree needs to change for the integration to function.

So the upstream engagement is not "merge an adapter into core" (their policy
closes those). It is: discussion first, then at most two small, format-perfect
PRs that give the plugin official surface area.

## Step 1 — open a Discussion/issue first

The PR template says: "If no issue exists, consider creating one first."

Draft title:

```
Integration: Fetch.ai uAgents bridge as a standalone plugin (hermes-fetch-ai)
```

Draft body (short form):

```
hermes-fetch-ai is a standalone plugin (pip package, `hermes_agent.plugins`
entry point) that exposes a default-deny, policy-gated subset of Hermes tools
to Fetch.ai uAgents over the published MCP protocol message models. Hermes
stays the local execution layer; Fetch supplies identity, signed envelopes,
addressing, and discovery rails.

- Zero Hermes core changes: CLI registers via ctx.register_cli_command;
  tool access goes through agent/transports/hermes_tools_mcp_server.py as an
  isolated stdio subprocess (shell=False, env allowlist, timeouts).
- Security defaults: only skills_list is public in the shipped config; every
  other exposed tool is denylisted; sender identity is routing evidence, not
  authorization; sizes/rates are capped; audit is redacted.
- The hermes mcp serve conversations surface is explicitly out of scope.

Repo: https://github.com/ptanner66-prog/Hermes-Fetch-AI (MIT)

Questions for maintainers:
1. Would you take an optional-skills/ entry that teaches the agent to drive
   `hermes fetchai` (rung-2 CLI-command-plus-skill pattern), or do you prefer
   this stays a Discord/Skills-Hub listed plugin?
2. Would a website/docs integration page be welcome, and under which section?
```

Do not open any PR before maintainer signal here, except a docs-only PR if
maintainers say docs PRs are always welcome.

## Step 2 — candidate PR A: optional skill (after maintainer signal)

Title:

```
feat(skills): add fetchai-bridge optional skill
```

Contents: `optional-skills/integrations/fetchai-bridge/SKILL.md` (+
`tests/skills/test_fetchai_bridge_skill.py`), following the HARDLINE skill
standards exactly:

- `description:` <= 60 chars, one sentence, ends with a period. Use:
  `Expose allowlisted Hermes tools to Fetch.ai uAgents.` (53 chars)
- Frontmatter `required_environment_variables` for `UAGENT_SEED` (hosted mode
  only), `prerequisites.commands: [hermes-fetch-ai]`.
- Section order: When to Use / Prerequisites / How to Run / Quick Reference /
  Procedure / Pitfalls / Verification; ~100 lines; no marketing words.
- Prose references native tools by backtick name; the bridge is invoked
  "through the `terminal` tool" as `hermes fetchai ...`.
- Tests: stdlib + pytest only, no network, frontmatter/description-length and
  section-order assertions, run via
  `scripts/run_tests.sh tests/skills/test_fetchai_bridge_skill.py -q`.
- `author:` credits the human contributor first.

## Step 3 — candidate PR B: website docs page (independent)

Title:

```
docs(website): add Fetch.ai uAgents bridge integration guide
```

One page under their docs integrations area: what the plugin does, install,
`hermes fetchai` commands, the security model (default deny, conversations
surface excluded), and a link back to this repo. No core claims, no
overreach; mirrors the README here.

## Ready-to-paste PR body (their template, filled)

```
## What does this PR do?

Adds an official optional skill for the standalone hermes-fetch-ai plugin,
which exposes a default-deny, policy-gated subset of Hermes tools to
Fetch.ai uAgents. Hermes remains the local execution layer; Fetch/uAgents
supplies identity, signed envelopes, addressing, and discovery. The plugin
registers `hermes fetchai ...` through the `hermes_agent.plugins` entry-point
group and drives the existing `agent/transports/hermes_tools_mcp_server.py`
stdio surface as an isolated subprocess — zero core changes, per the plugin
policy in AGENTS.md.

## Related Issue

Fixes #<discussion/issue number from Step 1>

## Type of Change

- [x] 🎯 New skill (bundled or hub)

## Changes Made

- `optional-skills/integrations/fetchai-bridge/SKILL.md` — skill instructions
- `tests/skills/test_fetchai_bridge_skill.py` — hermetic skill-format tests

## How to Test

1. `scripts/run_tests.sh tests/skills/test_fetchai_bridge_skill.py -q`
2. `pip install hermes-fetch-ai && hermes fetchai demo local` — expect
   `echo result: hello`, visible tool count 1, audit event count 4
3. `hermes --toolsets skills -q "Use the fetchai-bridge skill to check the
   bridge status"` — agent runs `hermes fetchai doctor` via `terminal`

## Checklist

### Code

- [x] I've read the Contributing Guide
- [x] My commit messages follow Conventional Commits
- [x] I searched for existing PRs to make sure this isn't a duplicate
- [x] My PR contains only changes related to this fix/feature
- [x] I've run `pytest tests/ -q` and all tests pass
- [x] I've added tests for my changes
- [x] I've tested on my platform: <fill in OS>

### Documentation & Housekeeping

- [x] I've updated relevant documentation — the SKILL.md is the doc
- [x] `cli-config.yaml.example` — N/A (no new config keys)
- [x] `CONTRIBUTING.md`/`AGENTS.md` — N/A (no architecture change)
- [x] Cross-platform impact considered — pure-Python plugin; the bridge
      supports Python 3.11/3.12 on Linux/macOS/Windows
- [x] Tool descriptions/schemas — N/A (no tool behavior change)

## For New Skills

- [x] Broadly useful as an official optional skill (agent-network reach for
      any Hermes install; not activated by default)
- [x] SKILL.md follows the standard format
- [x] No external dependencies beyond the plugin itself (stdlib + existing
      Hermes tools in prose; plugin invoked via `terminal`)
- [x] Tested end-to-end with `hermes --toolsets skills -q "..."`
```

## What we deliberately do NOT propose upstream

- An in-tree adapter directory (their May 2026 policy closes those).
- Any change to `run_agent.py`, `cli.py`, `gateway/run.py`, or core files.
- New model tools or toolsets (rung 6; not needed).
- New `HERMES_*` env vars (the bridge keeps secrets in its own env contract).
- Bridging the `hermes mcp serve` conversations surface (explicitly excluded;
  see `docs/security.md`).
