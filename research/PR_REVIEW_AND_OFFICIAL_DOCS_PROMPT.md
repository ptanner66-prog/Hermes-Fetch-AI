You are Hermes running an extensive PR review and official-docs pass.

Hermes repo:
C:\Users\ptann\OneDrive\Work\hermes-agent-main

Target repository:
C:\Users\ptann\OneDrive\Work\Hermes Fetch AI

Route constraint:
- ChatGPT-only.
- Model: gpt-5.5.
- Provider: openai-codex.
- API mode: codex_responses.
- Non-ChatGPT fallback providers are forbidden.
- Do not switch to gpt-5.3-codex-spark or any other model unless the operator explicitly says to switch.

Primary mission:
Run a rigorous Hermes reviewer-harness pass over the current Hermes Fetch AI PR/worktree and create official PR-ready docs. The end state should be Teknium-facing: high-signal findings, maintainer-native documentation, exact verification evidence, and a narrow upstream PR story.

Mode:
REVIEW PLUS DOCS AUTHORING.

Patch authority:
- Granted for documentation and review artifacts only.
- You may edit files under `docs/` and `research/`.
- You may update `README.md` only if needed to point to official docs.
- You may NOT edit implementation or tests in `src/`, `tests/`, `examples/`, `pyproject.toml`, `.github/`, or config files during this pass.
- If you find implementation/test defects, report them with exact file:line evidence and minimal fixes in the review report. Do not patch code in this run.

Before touching the target repo, read and follow:
- `C:\Users\ptann\OneDrive\Work\hermes-agent-main\codex\PROMPTING_GUIDE.md`
- `C:\Users\ptann\OneDrive\Work\hermes-agent-main\docs\hermes-reviewer-prompting.md`
- `C:\Users\ptann\OneDrive\Work\hermes-agent-main\OPERATOR-INBOX\clay\HERMES-LEASH-PROMPT-TEMPLATE.md`

Treat those prompting guides as binding: four-axis frame, review-first posture, durable artifacts, stop-and-ask/GAP discipline, self-audit loop, evidence-backed verdicts.

Review target:
- Current target repo branch and full dirty worktree.
- Include tracked modifications, untracked source/docs/tests/research files, and generated artifacts.
- Treat this as the PR candidate that will later become a simplified Hermes upstream PR.
- Do not assume current notes are accurate; verify from filesystem and command output.

Authority:
- User/operator decisions:
  - This is a connection project, not a reinvention project.
  - Fetch/uAgents/Agentverse/Almanac provide identity, discovery, addressing, endpoint/mailbox/proxy delivery, protocols, A2A launch surfaces, manifests, wallet/network context, and payment negotiation.
  - Hermes provides local intelligence, MCP, tools, safety, config, logging, plugins, and operator boundaries.
  - Thinnest reliable bridge.
  - ChatGPT-only routing; global model remains gpt-5.5 unless operator explicitly switches.
  - No OpenClaw content.
  - No legal-tech/private project content in public outputs.
  - No real FET movement without explicit operator approval.
- Local research:
  - `research/FINAL_ARCHITECTURE_DECISION.md`
  - `research/FULL_CONNECTION_GAP_AUDIT.md`
  - `research/MOE_HARDENING_REPORT.md`
  - `research/FETCH_FULL_CONNECTION_MAP.md`
  - `research/UPSTREAM_PR_EXECUTION_PLAN.md`
  - `research/TEKNIUM_PR_ONE_PAGER.md`
  - `research/NORMAL_HERMES_SECRET_TEST_RUNBOOK.md`
  - `research/NORMAL_HERMES_SECRET_TEST_STATUS.md`
  - `research/FET_TEST_FUNDS_PLAN.md`
  - `research/HOSTED_DEMO_BLOCKER.md`
  - `research/PAYMENT_OPERATOR_ACTIONS.md`
- Source docs and code:
  - Target repo files.
  - Local Hermes source checkout.
  - Fetch/uAgents/Agentverse official docs and GitHub source if web/GitHub access is available.

Risk lenses:
- Correctness and regression.
- Security, secret handling, trust boundaries, redaction, and audit logs.
- Hosted mailbox/proxy/endpoint behavior.
- Almanac manifest and protocol/model digest correctness.
- A2A compatibility decision.
- Payment rails: dry-run/testnet/real-value separation and explicit approval gates.
- Test adequacy and false-green risk.
- Maintainer-native upstream PR shape.
- Docs accuracy, source-backed claims, and stale/contradictory notes.
- Scope creep: no v1 marketplace/payment sprawl beyond disabled-by-default dry-run/testnet infrastructure.
- Contamination: no OpenClaw, no legal-tech/private content, no secrets.

Required process:
1. Create run directory `research/pr-review-official-docs/`.
   - Include `prompt.md`, `run-state.txt`, `compliance-matrix.md`, and raw command outputs as needed.
2. Set `run-state.txt` to `status=running`.
3. Inspect:
   - `git status --short --branch`
   - `git log --oneline -5`
   - `git diff --stat`
   - `git diff`
   - untracked file list and relevant untracked file contents
4. Review changed implementation files in full where behavior matters.
5. Review docs/research for contradictions.
6. Run or reuse with fresh verification when feasible:
   - `.venv\Scripts\python.exe -m pytest -q`
   - `ruff check .`
   - `python -m mypy src\hermes_fetch_ai --ignore-missing-imports`
   - `.venv\Scripts\python.exe -m hermes_fetch_ai.cli doctor --config examples\agentverse-mailbox-hermes.yaml --probe-backend`
   - `.venv\Scripts\python.exe -m hermes_fetch_ai.cli demo local`
   - `.venv\Scripts\python.exe -m hermes_fetch_ai.cli demo payment --config examples\payment-dry-run.yaml`
   - `.venv\Scripts\python.exe -m hermes_fetch_ai.cli doctor --config examples\agentverse-mailbox-hermes.yaml --contamination-scan`
   - mailbox without `UAGENT_SEED` should fail closed
7. Self-audit:
   - Re-read generated docs.
   - Confirm no secrets or private content.
   - Confirm no OpenClaw content.
   - Confirm docs do not overclaim hosted proof or payment settlement.
   - Confirm global route docs say gpt-5.5 and no fallback unless operator explicitly switches.
8. Before stopping, inspect final git status and run-state.

Required review artifacts:
1. `research/PR_REVIEW_REPORT.md`
   - Findings first, highest severity first.
   - Each finding must include file:line evidence, impact, and minimal fix.
   - Include GAPs separately from defects.
   - Include checks run and exact outcomes.
   - Include final verdict: GO, GO WITH WARNINGS, NO-GO, or BLOCKED.

2. `research/PR_REVIEW_STATUS.md`
   - Runtime model/provider/api_mode.
   - Files changed by this pass.
   - Commands run.
   - Whether implementation was edited (should be no).
   - Remaining operator-only blockers.

3. `research/UPSTREAM_PR_DESCRIPTION.md`
   - PR title.
   - Concise maintainer-facing summary.
   - What changed.
   - Why this belongs in Hermes.
   - Safety model.
   - Test plan.
   - Known limitations/operator-owned hosted steps.
   - Explicitly narrow upstream shape.

4. `research/UPSTREAM_PR_REVIEW_CHECKLIST.md`
   - Maintainer checklist.
   - Security checklist.
   - Fetch/Agentverse checklist.
   - Hermes MCP/tool policy checklist.
   - Payment/dry-run checklist.
   - Docs checklist.

Required official docs:
Create or update official user-facing docs under `docs/`:

1. `docs/fetch-uagents-bridge.md`
   - User-facing explanation of the Hermes Fetch/uAgents bridge.
   - Architecture and message flow.
   - Local demo.
   - Hermes MCP backend mode.
   - Mailbox/Agentverse hosted mode.
   - Trust boundaries and sender/tool policy.
   - What is and is not in v1.

2. `docs/agentverse-hosted-proof.md`
   - Operator runbook for Agentverse/mailbox hosted proof.
   - Safe local secret handling.
   - Exact PowerShell commands.
   - Stop points before funding, registration, or value movement.
   - Expected evidence.

3. `docs/payment-rails.md`
   - Dry-run payment negotiation.
   - Testnet/sandbox posture.
   - Real-FET approval gate.
   - What remains out of scope for v1.

4. Update `README.md` only if needed with short links to these docs.

Documentation rules:
- Public docs must be clean, maintainer-native, and not refer to "final boss", "babysitter", private legal-tech work, operator drama, or internal prompt machinery.
- Do not include secrets, seed examples that look real, private repo paths except where clearly local operator instructions already require paths, or screenshots.
- Use source-backed claims. If a Fetch/Agentverse claim is not verified, word it as a requirement or pending hosted proof, not a fact.
- Keep docs concise enough for maintainers.

Guardrails:
- No secret printing.
- Do not inspect `.env`.
- No real outbound hosted Agentverse actions unless explicitly operator-owned and already approved.
- No real FET movement.
- No production deploy.
- No force-push.
- No code/test changes in this pass.
- No OpenClaw content.
- No legal-tech/private project content in public docs.

Completion standards:
- Do not mark GO unless docs are written, review report exists, checks are run or exact blockers are recorded, and contradictions are resolved.
- If ChatGPT `gpt-5.5` quota is exhausted, stop and record BLOCKED_BY_CHATGPT_QUOTA. Do not switch models.
- If hosted proof is blocked on operator secrets/login, classify as EXTERNAL_OPERATOR_ONLY and keep local PR docs honest.
- Final run-state must be one of:
  - `status=completed_green`
  - `status=completed_yellow`
  - `status=completed_red`
  - `status=blocked_external_operator_only`
  - `status=blocked_chatgpt_quota`

Final handoff:
- Report verdict.
- List docs created/updated.
- List findings.
- List commands run and exact outcomes.
- List remaining blockers by local-actionable vs operator-only.
