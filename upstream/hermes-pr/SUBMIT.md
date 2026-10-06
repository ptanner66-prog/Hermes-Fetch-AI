# Submitting fetchai-bridge to the Hermes plugin catalog

Checked against Hermes 0.21.5 (tag `v2026.9.24`) and hermes-agent `main` at `bb236287`
(2026-10-06). Re-check before you submit; Hermes moves quickly. The plan, how the plugin
meets the admission rules, and the ready-to-paste PR text are in
[`docs/upstream-hermes-pr.md`](../../docs/upstream-hermes-pr.md).

The submission is one file, [`plugin-catalog/fetchai-bridge.yaml`](plugin-catalog/fetchai-bridge.yaml),
added to NousResearch/hermes-agent with its `sha` filled in. Submit it from the repository
owner's account (catalog rule 5).

## 1. Pick the commit to pin

1. Bump the version past the last release, in `pyproject.toml`, `plugin.yaml`,
   `PLUGIN_VERSION` in `hermes-plugin/fetchai-bridge/__init__.py`, and the entry's `version`
   (a test keeps them equal), and set the date in `CHANGELOG.md`.
2. Merge to `main` here and wait for CI to pass on the merge commit, including both
   `hermes plugin + field test` jobs. Run the "Live testnet" workflow on it too.
3. Get the full SHA: `git fetch origin main && git rev-parse origin/main`.
4. Tag `v<version>` on that commit and push the tag. This is required: `hermes fetchai-bridge
   install` installs the bridge from that tag. Never move it afterwards. The catalog pins
   the plugin by SHA.

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
git -c user.name=ptanner66-prog \
    -c user.email=236672476+ptanner66-prog@users.noreply.github.com \
    commit -m "feat(plugin-catalog): add fetchai-bridge"
```

- **Author email:** Hermes' contributor check fails on commit emails it cannot map to a
  GitHub account. The commit above uses your GitHub noreply address, which the check
  resolves on its own and which keeps your personal email out of hermes-agent. (The
  check's other fix, `scripts/add_contributor.py`, adds a file named after your email to
  the repository.)
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
- No mainnet money. Payments run on Fetch's testnet only, and Hermes' buying tools pay only
  after the user accepts Hermes' confirmation prompt, within the bridge's per-payment,
  per-seller, and daily limits. Almanac contract registration, which can pay fees from the
  agent's wallet, is off unless configured. The entry, the PR body, and the plugin README
  disclose all of this.
- No conversations/messaging surface; the bridge reaches only the Hermes tools MCP
  server, allowlisted and in a separate process.
- If a maintainer ever asks for an in-tree optional skill instead, start from the plugin's
  [`skills/operate/SKILL.md`](../../hermes-plugin/fetchai-bridge/skills/operate/SKILL.md).
