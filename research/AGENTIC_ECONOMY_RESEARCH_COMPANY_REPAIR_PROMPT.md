You are Hermes continuing the Hermes Fetch AI agentic-economy research-company run.

Working directory:
C:\Users\ptann\OneDrive\Work\Hermes Fetch AI

Route constraint:
- ChatGPT-only.
- Model: gpt-5.5.
- Provider: openai-codex.
- API mode: codex_responses.
- `fallback_providers=[]`.
- Do not switch models unless the operator explicitly says to switch.
- If gpt-5.5 quota is exhausted, stop and record `BLOCKED_BY_CHATGPT_QUOTA`.

Mission:
Complete the prior research-company run. Do not repeat external collection unless an existing source is unusable. Use the existing raw source cache and notes in:

`research/agentic-economy-research-company/`

The prior run ended after collecting sources and writing a strong summary into:

`research/agentic-economy-research-company-run.log`

It did not write the required final artifacts. Your job is to write them, run verification, self-audit them, and set the run state honestly.

Patch authority:
- You may edit `research/**`, `docs/**`, and `README.md`.
- You may not edit implementation, tests, examples, pyproject, CI, or Hermes source in this pass.
- If code/test issues are found, record them in review artifacts with file:line evidence and minimal fix. Do not patch code.

Required first steps:
1. Read `research/AGENTIC_ECONOMY_RESEARCH_COMPANY_PROMPT.md`.
2. Read `research/agentic-economy-research-company-run.log`, especially the sections:
   - Strong thesis emerging from evidence.
   - Security/trust findings.
   - Payment/economic findings.
   - Work not completed.
   - Verification not completed.
   - Recommended next safe action.
3. Inspect `research/agentic-economy-research-company/raw/`.
4. Populate/update:
   - `research/agentic-economy-research-company/source-ledger.md`
   - `research/agentic-economy-research-company/compliance-matrix.md`
   - `research/agentic-economy-research-company/run-state.txt`

Required research artifacts:
- `research/AGENTIC_ECONOMY_MASTER_REPORT.md`
- `research/FETCH_RAILS_DEEP_MAP.md`
- `research/HERMES_AS_FETCH_AGENT_BLUEPRINT.md`
- `research/AGENTIC_ECONOMY_PRODUCT_STRATEGY.md`
- `research/PAYMENT_AND_INCENTIVE_RAILS_STRATEGY.md`
- `research/SECURITY_TRUST_AND_GOVERNANCE_MODEL.md`
- `research/UPSTREAM_PR_PACKAGE_PLAN.md`
- `research/AGENTIC_ECONOMY_ADVERSARIAL_REVIEW.md`
- `research/UPSTREAM_PR_DESCRIPTION.md`
- `research/UPSTREAM_PR_REVIEW_CHECKLIST.md`
- `research/PR_REVIEW_REPORT.md`
- `research/PR_REVIEW_STATUS.md`

Required public docs:
- `docs/fetch-uagents-bridge.md`
- `docs/agentverse-hosted-proof.md`
- `docs/payment-rails.md`
- `docs/agentic-economy-thesis.md`

Update `README.md` only if needed with concise links to the official docs.

Required content standards:
- Thesis: Hermes is the agent runtime; Fetch/uAgents/Agentverse/Almanac are the rails.
- Keep it concrete and source-backed, not hype.
- Treat Agentverse/uAgent identity as identity, not trust.
- Keep v1 thin: no marketplace sprawl, no wallet custody, no real-FET movement without explicit operator approval.
- Distinguish local proof, hosted proof, dry-run payment, testnet/sandbox, and real-value/mainnet.
- Do not overclaim hosted proof or payment settlement.
- No OpenClaw content.
- No legal-tech/private project content in public docs.
- No secrets.
- Do not inspect `.env`.

Verification commands:
Run and capture exact outcomes unless blocked:
- `git status --short --branch`
- `git diff --stat`
- `.venv\Scripts\python.exe -m pytest -q`
- `ruff check .`
- `python -m mypy src\hermes_fetch_ai --ignore-missing-imports`
- `.venv\Scripts\python.exe -m hermes_fetch_ai.cli doctor --config examples\agentverse-mailbox-hermes.yaml --probe-backend`
- `.venv\Scripts\python.exe -m hermes_fetch_ai.cli demo local`
- `.venv\Scripts\python.exe -m hermes_fetch_ai.cli demo payment --config examples\payment-dry-run.yaml`
- `.venv\Scripts\python.exe -m hermes_fetch_ai.cli doctor --config examples\agentverse-mailbox-hermes.yaml --contamination-scan`
- `.venv\Scripts\python.exe -m hermes_fetch_ai.cli demo mailbox --config examples\agentverse-mailbox-hermes.yaml --duration-seconds 5` with no `UAGENT_SEED`; this should fail closed.

Self-audit:
- Re-read all created docs and artifacts.
- Verify no private paths leak into public docs except necessary local runbook paths.
- Verify no secrets or `.env` content.
- Verify no OpenClaw/private legal-tech content.
- Verify source claims cite URLs or local files.
- Verify final `git status --short --branch`.

Final run-state:
Set `research/agentic-economy-research-company/run-state.txt` to one of:
- `status=completed_green`
- `status=completed_yellow`
- `status=completed_red`
- `status=blocked_external_operator_only`
- `status=blocked_chatgpt_quota`

Final response/log should summarize:
- Verdict.
- Artifacts created.
- Docs created.
- Verification commands and exact outcomes.
- Remaining operator-only steps.
