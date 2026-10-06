# Submitting fetchai-bridge to the Hermes plugin catalog

Checked against Hermes 0.21.5 (tag `v2026.9.24`) and hermes-agent `main` at `bb236287`
(2026-10-06). Re-check before you submit; Hermes moves quickly. The plan, how the plugin
meets the admission rules, and the ready-to-paste PR text are in
[`docs/upstream-hermes-pr.md`](../../docs/upstream-hermes-pr.md).

The submission is one file, [`plugin-catalog/fetchai-bridge.yaml`](plugin-catalog/fetchai-bridge.yaml),
added to NousResearch/hermes-agent with its `sha` filled in. Submit it from the repository
owner's account (catalog rule 5).

## 1. Pick the commit to pin

1. Merge the plugin to `main` here and wait for CI to pass on the merge commit, including
   both `hermes plugin + field test` jobs.
2. Get the full SHA: `git fetch origin main && git rev-parse origin/main`.
3. Optionally tag `v1.0.0` on that commit. The catalog still pins the SHA.

## 2. Re-run the catalog checks at that commit

```bash
git clone https://github.com/ptanner66-prog/Hermes-Fetch-AI /tmp/fetchai-pin
git -C /tmp/fetchai-pin checkout <sha>
hermes plugins validate /tmp/fetchai-pin/hermes-plugin/fetchai-bridge --install-deps
```

Expect `Validation passed.` with `security scan — safe`. Then check that `version` in the
entry matches `plugin.yaml` at that commit, and that `requires_hermes` is not newer than
the latest Hermes release (rule 14).

## 3. Seed safety

- `UAGENT_SEED` lives only in the environment or Hermes' `.env`. Never in YAML, the entry,
  commits, PR text, screenshots, or terminal output you paste.
- Use a dedicated agent seed (at least 32 random characters), not a wallet recovery
  phrase that guards real holdings.
- Before pushing: `git diff origin/main... | grep -iE "seed|secret|mnemonic"` should show
  nothing real.

## 4. Open the PR

```bash
cd <your fork of hermes-agent>
git checkout -b feat/plugin-catalog-fetchai-bridge
cp <this-repo>/upstream/hermes-pr/plugin-catalog/fetchai-bridge.yaml plugin-catalog/
# Replace REPLACE_WITH_THE_40_CHARACTER_COMMIT_SHA with the SHA from step 1.
python3 scripts/validate_plugin_catalog.py plugin-catalog/fetchai-bridge.yaml   # needs ruamel.yaml
git add plugin-catalog/fetchai-bridge.yaml
git commit -m "feat(plugin-catalog): add fetchai-bridge"
```

- **Author email:** Hermes' contributor check fails on unmapped commit emails. Commit as
  `236672476+ptanner66-prog@users.noreply.github.com`, or add your email with
  `python3 scripts/add_contributor.py <email> ptanner66-prog` in the same PR.
- **PR title and body:** "Ready-to-paste catalog PR" in `docs/upstream-hermes-pr.md`.
- **CI:** wait for the `plugin-catalog-ci` checks. They clone this repository at the pin
  and run `hermes plugins validate --install-deps` on `hermes-plugin/fetchai-bridge`.
- **Review:** a maintainer may rewrite the entry's `Disclosure —` sentence or ask for
  changes. Fix them here, re-pin, and update the PR.

## Later updates

A new pin is a new PR (rule 4) that bumps `sha` and `version` together. Reviewers read the
commit range being adopted, so keep plugin changes small and described in `CHANGELOG.md`.

## What this submission is not

- No Hermes core changes and no self-updating code.
- No funds-moving code. The bridge's wallet derives from `UAGENT_SEED`; when Almanac
  registration is enabled, uAgents' default registration policy may pay its fee from that
  wallet.
- No conversations/messaging surface; the bridge reaches only the Hermes tools MCP
  server, allowlisted and in a separate process.
- If a maintainer ever asks for an in-tree optional skill instead, start from the plugin's
  [`skills/operate/SKILL.md`](../../hermes-plugin/fetchai-bridge/skills/operate/SKILL.md).
