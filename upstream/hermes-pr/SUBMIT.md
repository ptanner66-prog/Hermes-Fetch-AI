# Submitting the fetchai-bridge skill to NousResearch/hermes-agent

Payload in this directory, already validated against the real hermes-agent
repo on 2026-06-10: their pytest ran the skill test (`5 passed in 0.69s`),
their `scripts/check-windows-footguns.py` reported no findings, and the
frontmatter description passes the HARDLINE 60-char rule (52 chars).

## Before you touch anything: seed safety

- `UAGENT_SEED` lives ONLY in the environment or `~/.hermes/.env`. Never in
  YAML, SKILL.md, commits, PR text, screenshots, or terminal output you paste.
- Use a dedicated agent seed, not a wallet recovery phrase that guards real
  holdings. Fund the derived `fetch1...` address with only what Almanac
  registration needs.
- This repo enforces the boundary (config rejects secret-shaped values,
  mailbox mode fails closed, logs redact seeds), but nothing can protect a
  seed pasted into a PR description. Final check before pushing:
  `git diff origin/main... | grep -iE "seed|secret|mnemonic"` should show
  nothing real.

## Author credit

Already set per their rule (human first): `author: Porter Tanner (ptanner66-prog)`.
The install instruction uses the git URL because the package is not on PyPI yet;
if you publish `hermes-fetch-ai` to PyPI first, simplify that line.

## Submission steps

```bash
cd <hermes-agent checkout>
git checkout -b feat/skills-fetchai-bridge

mkdir -p optional-skills/autonomous-ai-agents/fetchai-bridge
cp <this-repo>/upstream/hermes-pr/optional-skills/autonomous-ai-agents/fetchai-bridge/SKILL.md \
   optional-skills/autonomous-ai-agents/fetchai-bridge/SKILL.md
cp <this-repo>/upstream/hermes-pr/tests/skills/test_fetchai_bridge_skill.py \
   tests/skills/test_fetchai_bridge_skill.py

python -m pytest tests/skills/test_fetchai_bridge_skill.py -q   # expect 5 passed
python scripts/check-windows-footguns.py                        # expect no findings

git add optional-skills/autonomous-ai-agents/fetchai-bridge tests/skills/test_fetchai_bridge_skill.py
git commit -m "feat(skills): add fetchai-bridge optional skill"
git push -u origin feat/skills-fetchai-bridge
```

PR title:

```
feat(skills): add fetchai-bridge optional skill
```

PR body: use the filled template in `docs/upstream-hermes-pr.md` (section
"Ready-to-paste PR body"), updating the issue number and your platform line.
As a maintainer-side contributor you may skip the discussion-first step, but
the body still links the plugin repo and states the security model.

## What this PR deliberately is not

- No Hermes core-file changes (their plugin policy forbids them; none needed).
- No funds-moving code. FET spending works through standard uAgents rails:
  the bridge agent's wallet derives from `UAGENT_SEED` (cosmpy `LedgerClient`,
  `fetch1...` address) and uAgents' default registration policy pays the
  Almanac fee from that wallet in hosted mode. Verified in
  `tests/test_uagent_direct_protocol.py::test_build_agent_keeps_ledger_registration_policy_when_publishing`.
- No conversations/messaging surface; the bridge only reaches the Hermes
  tools MCP server, allowlisted and in a separate process.
