# Hermes Overnight Until-Done Report

Updated: 2026-05-18T03:46:22Z
Route: ChatGPT-only; model=gpt-5.5; provider=openai-codex; api_mode=codex_responses; fallback_providers=[]
Final status: BLOCKED_OPERATOR_ONLY

## Summary

The prior BLOCKED_OPERATOR_ONLY state was challenged with another adversarial local pass. That pass found repo-local hardening work and fixed it before accepting any blocker classification.

Final classification remains BLOCKED_OPERATOR_ONLY because local gates are green and the only remaining work now requires operator-owned account login, process-local seed/credentials, hosted Agentverse/mailbox setup, optional explicitly authorized payment proof, or PR/merge authority.

No .env file was inspected. No hosted Agentverse/ASI path was called. No seed, private signing material, mailbox key, API token, wallet secret, or recovery material was requested or printed. No real FET moved and no testnet/mainnet transaction was attempted.

Codex follow-up after the Hermes run exited: independent verification found one remaining local test-isolation issue. `tests/test_mailbox_startup.py::test_mailbox_config_requires_env_seed` expected the missing `UAGENT_SEED` failure but did not set `HERMES_FETCH_HERMES_PYTHON`, so the newer fail-closed env expansion correctly failed earlier. Codex fixed the test to set `HERMES_FETCH_HERMES_PYTHON=python` and reran the local gates. The blocker classification is still BLOCKED_OPERATOR_ONLY after this fix.

## Repo-local issues found and fixed

1. Seed/env fail-closed behavior
   - Rejected `agent.seed` and `agent.mailbox_key` in config/direct model input instead of accepting config-carried identity material.
   - Removed the prior `dev-` YAML seed exception: YAML seed values are rejected even when dev-prefixed.
   - Made `effective_seed()` fail closed without non-blank `UAGENT_SEED` when `agent.dev_random_seed=false`; it no longer falls back to YAML or an empty string.
   - Mailbox/proxy modes now reject `dev_random_seed=true` because remote-facing identities require a stable operator-owned seed.
   - Stdio env expansion now fails if a referenced env var is missing, rejects secret-shaped env var names, and rejects secret-shaped expanded values.

2. Payment safety
   - `payment.mode=testnet` is now an operator stop in config validation, matching the docs that testnet/sandbox proof is future/operator-approved and not automatic.
   - `payment.mode=real_operator_approved` remains an operator stop.
   - `PaymentDryRunStore` now only accepts `payment.mode=dry_run` configs.
   - Dry-run commit cancellation for unknown references now returns a shortened transaction id instead of echoing a full transaction-like value.
   - Dry-run commits still accept only `dryrun-*` transaction ids and do not touch wallets/chains/processors.

3. Contamination coverage
   - Public-tree contamination tests now include the same broader forbidden categories used by the CLI scan.
   - Added test coverage for the CLI contamination scan itself.
   - Research/raw/background files remain out of the public release-tree scan; public `src`, `docs`, `examples`, `README.md`, `.env.example`, and `pyproject.toml` scan clean.

## Files changed in this pass

- src/hermes_fetch_ai/config.py
- src/hermes_fetch_ai/payments.py
- tests/test_config.py
- tests/test_payment_policy.py
- tests/test_contamination.py
- tests/test_mailbox_startup.py
- research/HERMES_OVERNIGHT_UNTIL_DONE_STATUS.md
- research/HERMES_OVERNIGHT_UNTIL_DONE_REPORT.md
- research/HERMES_CODEX_DONE_STATUS.md
- research/HERMES_CODEX_DONE_AGREEMENT.md
- research/OPERATOR_ACTIONS_TO_FINISH.md
- research/PR_REVIEW_STATUS.md
- research/PR_REVIEW_REPORT.md
- research/agentic-economy-research-company/run-state.txt

Note: the worktree already contained many tracked/untracked changes from earlier passes; this report records the current state rather than claiming every listed dirty path was changed only in this final pass.

## Codex follow-up verification

After the Hermes process exited, Codex reran the local acceptance gates. First pytest run failed on `tests/test_mailbox_startup.py::test_mailbox_config_requires_env_seed` because the test did not set `HERMES_FETCH_HERMES_PYTHON`, so config validation failed on the missing stdio command env var before reaching the intended `UAGENT_SEED` assertion. Codex patched that test and reran:

- `.venv\Scripts\python.exe -m pytest -q`: exit 0, `92 passed in 19.50s`
- `ruff check .`: exit 0, `All checks passed!`
- `python -m mypy src\hermes_fetch_ai --ignore-missing-imports`: exit 0, `Success: no issues found in 20 source files`
- with `HERMES_FETCH_HERMES_PYTHON=C:\Users\ptann\OneDrive\Work\hermes-agent-main\.venv\Scripts\python.exe`, `doctor --probe-backend`: exit 0, `backend: ok: 10 tools`, `doctor: ok`
- `demo local`: exit 0, visible tool count `1`, echo result `hello`, audit event count `4`
- `demo payment --config examples\payment-dry-run.yaml`: exit 0, dry-run request/accept/complete path succeeded and no real funds moved
- `doctor --contamination-scan`: exit 0, `contamination: ok`, `doctor: ok`
- mailbox demo with no `UAGENT_SEED`: exit 1 as expected, fail-closed on `UAGENT_SEED is required when agent.dev_random_seed=false`

## Exact command outcomes

All commands were run from `C:\Users\ptann\OneDrive\Work\Hermes Fetch AI` through the available bash-compatible terminal. Windows venv executables were invoked as `.venv/Scripts/python.exe` where needed.

### git status --short --branch

Command:

```text
git status --short --branch
```

Exit: 0

Output:

```text
## codex/full-hookup-proof
 M README.md
 M docs/demo.md
 M docs/security.md
 M docs/troubleshooting.md
 M research/FINAL_ARCHITECTURE_DECISION.md
 M research/FULL_HOOKUP_STATUS.md
 M src/hermes_fetch_ai/_redaction.py
 M src/hermes_fetch_ai/arg_validator.py
 M src/hermes_fetch_ai/audit.py
 M src/hermes_fetch_ai/cli.py
 M src/hermes_fetch_ai/config.py
 M src/hermes_fetch_ai/direct_protocol.py
 M src/hermes_fetch_ai/mcp_shim.py
 M src/hermes_fetch_ai/uagent_app.py
 M tests/test_config.py
 M tests/test_contamination.py
?? docs/agentic-economy-thesis.md
?? docs/agentverse-hosted-proof.md
?? docs/fetch-uagents-bridge.md
?? docs/payment-rails.md
?? examples/agentverse-mailbox-hermes.yaml
?? examples/payment-dry-run.yaml
?? research/AGENTIC_ECONOMY_ADVERSARIAL_REVIEW.md
?? research/AGENTIC_ECONOMY_MASTER_REPORT.md
?? research/AGENTIC_ECONOMY_PRODUCT_STRATEGY.md
?? research/AGENTIC_ECONOMY_RESEARCH_COMPANY_PROMPT.md
?? research/AGENTIC_ECONOMY_RESEARCH_COMPANY_REPAIR_PROMPT.md
?? research/FETCH_FULL_CONNECTION_MAP.md
?? research/FETCH_GITHUB_SWEEP.md
?? research/FETCH_RAILS_DEEP_MAP.md
?? research/FET_TEST_FUNDS_PLAN.md
?? research/FINAL_BOSS_HERMES_PROMPT.md
?? research/FINAL_BOSS_STATUS.md
?? research/FULL_CONNECTION_A2A_AGENTVERSE_ADDENDUM.md
?? research/FULL_CONNECTION_ALMANAC_ADDENDUM.md
?? research/FULL_CONNECTION_FETCH_WEBSITE_ADDENDUM.md
?? research/FULL_CONNECTION_GAP_AUDIT.md
?? research/HERMES_AS_FETCH_AGENT_BLUEPRINT.md
?? research/HERMES_CODEX_DONE_AGREEMENT.md
?? research/HERMES_CODEX_DONE_AGREEMENT_PROMPT.md
?? research/HERMES_CODEX_DONE_STATUS.md
?? research/HERMES_OVERNIGHT_UNTIL_DONE_PROMPT.md
?? research/HERMES_OVERNIGHT_UNTIL_DONE_REPORT.md
?? research/HERMES_OVERNIGHT_UNTIL_DONE_STATUS.md
?? research/HERMES_UPSTREAM_SWEEP.md
?? research/HOSTED_DEMO_BLOCKER.md
?? research/HOSTED_FET_OPERATOR_WALKTHROUGH_PROMPT.md
?? research/MOE_HARDENING_REPAIR_PROMPT.md
?? research/MOE_HARDENING_REPORT.md
?? research/MOE_HARDENING_STATUS.md
?? research/MOE_RESEARCH_HARDENING_PROMPT.md
?? research/NORMAL_HERMES_SECRET_FULL_TEST_PROMPT.md
?? research/NORMAL_HERMES_SECRET_TEST_RUNBOOK.md
?? research/NORMAL_HERMES_SECRET_TEST_STATUS.md
?? research/NOUS_HERMES_PR_STYLE_REVIEW.md
?? research/OPERATOR_ACTIONS_TO_FINISH.md
?? research/PAYMENT_AND_INCENTIVE_RAILS_STRATEGY.md
?? research/PAYMENT_OPERATOR_ACTIONS.md
?? research/PAYMENT_RAILS_RESEARCH.md
?? research/PR_REVIEW_AND_OFFICIAL_DOCS_PROMPT.md
?? research/PR_REVIEW_REPORT.md
?? research/PR_REVIEW_STATUS.md
?? research/SECURITY_TRUST_AND_GOVERNANCE_MODEL.md
?? research/SOURCE_ACCESS_LOG.md
?? research/TEKNIUM_PR_ONE_PAGER.md
?? research/UPSTREAM_PR_DESCRIPTION.md
?? research/UPSTREAM_PR_EXECUTION_PLAN.md
?? research/UPSTREAM_PR_PACKAGE_PLAN.md
?? research/UPSTREAM_PR_REVIEW_CHECKLIST.md
?? research/agentic-economy-research-company-repair-runner.py
?? research/agentic-economy-research-company-runner.py
?? research/agentic-economy-research-company/
?? research/hermes-codex-done-agreement-runner.py
?? research/hermes-overnight-until-done-runner.py
?? research/normal-hermes-secret-full-test-runner.py
?? research/pr-review-official-docs-runner.py
?? research/pr-review-official-docs/
?? src/hermes_fetch_ai/payment_policy.py
?? src/hermes_fetch_ai/payment_protocol.py
?? src/hermes_fetch_ai/payments.py
?? tests/test_mailbox_startup.py
?? tests/test_payment_demo.py
?? tests/test_payment_policy.py
```

### git diff --stat

Command:

```text
git diff --stat
```

Exit: 0

Output:

```text
warning: in the working copy of 'research/FINAL_ARCHITECTURE_DECISION.md', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'research/FULL_HOOKUP_STATUS.md', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'src/hermes_fetch_ai/arg_validator.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'src/hermes_fetch_ai/cli.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'src/hermes_fetch_ai/mcp_shim.py', LF will be replaced by CRLF the next time Git touches it
 README.md                               |  79 ++++++-----
 docs/demo.md                            |  25 +++-
 docs/security.md                        |  10 ++
 docs/troubleshooting.md                 |   8 ++
 research/FINAL_ARCHITECTURE_DECISION.md | 239 ++++++++++++++------------------
 research/FULL_HOOKUP_STATUS.md          |  59 +++++---
 src/hermes_fetch_ai/_redaction.py       |  22 ++-
 src/hermes_fetch_ai/arg_validator.py    |  68 ++-------
 src/hermes_fetch_ai/audit.py            |   7 +
 src/hermes_fetch_ai/cli.py              | 140 ++++++++++++++++---
 src/hermes_fetch_ai/config.py           | 200 ++++++++++++++++++++++----
 src/hermes_fetch_ai/direct_protocol.py  |  15 +-
 src/hermes_fetch_ai/mcp_shim.py         |  11 +-
 src/hermes_fetch_ai/uagent_app.py       | 171 +++++++++++++++++++++--
 tests/test_config.py                    | 105 ++++++++++++++
 tests/test_contamination.py             |  38 +++--
 16 files changed, 879 insertions(+), 318 deletions(-)
```

Note: `git diff --stat` does not include untracked files such as new docs/research/examples/payment files.

### pytest

Command:

```text
.venv/Scripts/python.exe -m pytest -q
```

Exit: 0

Output:

```text
........................................................................ [ 78%]
....................                                                     [100%]
92 passed in 18.01s
```

### ruff

Command:

```text
ruff check .
```

Exit: 0

Output:

```text
All checks passed!
```

### mypy

Command:

```text
python -m mypy src/hermes_fetch_ai --ignore-missing-imports
```

Exit: 0

Output:

```text
Success: no issues found in 20 source files
```

### Hermes backend probe through mailbox config

Command:

```text
HERMES_FETCH_HERMES_PYTHON='C:\Users\ptann\OneDrive\Work\hermes-agent-main\.venv\Scripts\python.exe' .venv/Scripts/python.exe -m hermes_fetch_ai.cli doctor --config examples/agentverse-mailbox-hermes.yaml --probe-backend
```

Exit: 0

Output:

```text
backend: ok: 10 tools
doctor: ok
```

### Local demo

Command:

```text
.venv/Scripts/python.exe -m hermes_fetch_ai.cli demo local
```

Exit: 0

Output:

```text
bridge address: agent1qvlsvygmvdh9rufnx5fynt2v8lr4w95z4w92960gghg9t7qtzgzsqkszvlh
visible tool count: 1
echo result: hello
audit event count: 4
```

### Payment dry-run demo

Command:

```text
.venv/Scripts/python.exe -m hermes_fetch_ai.cli demo payment --config examples/payment-dry-run.yaml
```

Exit: 0

Output:

```text
payment dry-run: request created
payment dry-run: reference: hfa-5156648954e3ddd8fab685ae
payment dry-run: accepted: 0.01 FET via fet_direct
payment dry-run: commit decision: complete
payment dry-run: completion: CompletePayment
payment dry-run: audit event count: 2
payment dry-run: no real funds moved; no wallet secret or FET spend used
```

### Contamination scan

Command:

```text
.venv/Scripts/python.exe -m hermes_fetch_ai.cli doctor --config examples/agentverse-mailbox-hermes.yaml --contamination-scan
```

Exit: 0

Output:

```text
contamination: ok
doctor: ok
```

### Mailbox demo with no UAGENT_SEED

Command:

```text
env -u UAGENT_SEED HERMES_FETCH_HERMES_PYTHON='C:\Users\ptann\OneDrive\Work\hermes-agent-main\.venv\Scripts\python.exe' .venv/Scripts/python.exe -m hermes_fetch_ai.cli demo mailbox --config examples/agentverse-mailbox-hermes.yaml --duration-seconds 1
```

Exit: 1 (expected fail-closed negative proof)

Output:

```text
mailbox demo: FAIL: 1 validation error for BridgeConfig
  Value error, UAGENT_SEED is required when agent.dev_random_seed=false [type=value_error, input_value={'version': 1, 'agent': {... {'enable_chat': False}}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/value_error
mailbox demo: set UAGENT_SEED only in the operator shell and see research/HOSTED_DEMO_BLOCKER.md
```

## Residual blockers

Operator-owned only:

1. Hosted Agentverse/mailbox proof with operator account/login, mailbox or endpoint setup, process-local `UAGENT_SEED`, remote sender/linking, and a sanitized transcript.
2. Optional testnet/sandbox payment proof only after a named rail, exact max amount/currency, recipient, process-local credentials/wallet setup, and explicit current-context authorization.
3. Real-value/mainnet payment remains out of automatic scope and requires separate explicit current-context authorization plus custody, fee, legal/commercial/security, and incident planning.
4. Human review/PR/merge/commit authority for the dirty working tree.

First operator action after waking: review `research/OPERATOR_ACTIONS_TO_FINISH.md`, then decide whether to run the hosted Agentverse/mailbox proof using the safe process-local seed flow or to package/review the dirty tree for a PR.
