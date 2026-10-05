# Submitting fetchai-bridge to NousResearch/hermes-agent

Checked against hermes-agent `main` at `bb236287` (2026-10-05). Re-check before you
submit; Hermes moves quickly. The full plan, including which route to take and
ready-to-paste text, is in [`docs/upstream-hermes-pr.md`](../../docs/upstream-hermes-pr.md).

## Pick the route first

Hermes' `CONTRIBUTING.md` says third-party product integrations ship as standalone
plugins, and niche or community skills belong on the Skills Hub. An
`optional-skills/` PR for this bridge is therefore likely to be redirected even if CI
passes. In order of fit:

1. **Plugin catalog entry** (`plugin-catalog/<name>.yaml`, pinned to a full commit
   SHA). Needs the repo work listed in `docs/upstream-hermes-pr.md` first.
2. **Skills Hub**: publish this `SKILL.md` to a skills registry and share it in the
   Nous Research Discord. No hermes-agent PR needed.
3. **`optional-skills/` PR** (steps below), after a GitHub Discussion where a
   maintainer says they want it in-tree.

## Before you touch anything: seed safety

- `UAGENT_SEED` lives ONLY in the environment or a `0600` env file. Never in YAML,
  SKILL.md, commits, PR text, screenshots, or terminal output you paste.
- Use a dedicated agent seed (at least 32 random characters), not a wallet recovery
  phrase that guards real holdings. Fund the derived `fetch1...` address with only
  what Almanac registration needs.
- Final check before pushing:
  `git diff origin/main... | grep -iE "seed|secret|mnemonic"` should show nothing real.

## Route 3: optional-skills PR steps

```bash
cd <your fork of hermes-agent>
git checkout -b feat/skills-fetchai-bridge

mkdir -p optional-skills/autonomous-ai-agents/fetchai-bridge
cp <this-repo>/upstream/hermes-pr/optional-skills/autonomous-ai-agents/fetchai-bridge/SKILL.md \
   optional-skills/autonomous-ai-agents/fetchai-bridge/SKILL.md
# Replace <full-commit-sha> in SKILL.md with the 40-character commit you want users on.

# The docs site is generated from skills; commit what this changes
# (optional-skills catalog row, a new skill page, one sidebars.ts line).
python3 website/scripts/generate-skill-docs.py

git add optional-skills/autonomous-ai-agents/fetchai-bridge website/
python scripts/check-windows-footguns.py        # scans staged files only
python scripts/check                            # the blocking lint CI runs
scripts/run_tests.sh tests/skills/              # repo-wide skill rules
```

- **Author email:** Hermes' contributor check fails on unmapped commit emails. Commit
  as `236672476+ptanner66-prog@users.noreply.github.com`, or add your email with
  `python3 scripts/add_contributor.py <email> ptanner66-prog` in the same PR.
- **Commit message:** `feat(skills): add fetchai-bridge optional skill`
  (Conventional Commits).
- **End-to-end check** the PR template asks for:
  `hermes --toolsets skills -q "Use the fetchai-bridge skill to run the local demo"`.
- **PR body:** use "Ready-to-paste PR body" in `docs/upstream-hermes-pr.md`.

This payload no longer ships its own test: Hermes' repo-wide skill tests already
enforce frontmatter and description rules, and `tests/AGENTS.md` asks reviewers to
reject change-detector tests (the old one broke on a wording change).

## What this PR deliberately is not

- No Hermes core-file changes (their plugin policy forbids them; none needed).
- No funds-moving code. FET spending works through standard uAgents rails: the
  bridge agent's wallet derives from `UAGENT_SEED` and uAgents' default registration
  policy pays the Almanac fee from that wallet in hosted mode. Verified in
  `tests/test_uagent_direct_protocol.py::test_build_agent_keeps_ledger_registration_policy_when_publishing`.
- No conversations/messaging surface; the bridge only reaches the Hermes tools MCP
  server, allowlisted and in a separate process.
