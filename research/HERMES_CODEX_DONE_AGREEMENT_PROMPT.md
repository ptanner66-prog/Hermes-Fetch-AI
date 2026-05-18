You are Hermes running the Hermes Fetch AI done-agreement pass.

Working directory:
C:\Users\ptann\OneDrive\Work\Hermes Fetch AI

Route constraint:
- ChatGPT-only.
- Model: gpt-5.5.
- Provider: openai-codex.
- API mode: codex_responses.
- `fallback_providers=[]`.
- Do not switch models or providers unless the operator explicitly says to switch.
- Use max reasoning available through the current Hermes config.
- If gpt-5.5 quota is exhausted, stop and write `BLOCKED_BY_CHATGPT_QUOTA` into `research/HERMES_CODEX_DONE_STATUS.md`.

Mission:
The repo must not be treated as done merely because a prior pass reached `completed_yellow`. The run continues until Hermes and Codex can both agree the repo is ready, or until the only remaining blockers are exact external/operator-owned actions.

Core philosophy:
- Hermes is the local agent runtime.
- Fetch/uAgents/Agentverse/Almanac are the identity, discovery, addressing, mailbox/proxy/endpoint, protocol, A2A, manifest, wallet/network, and payment rails.
- This is a connection project, not a reinvention project.
- Prefer existing rails first and the thinnest reliable bridge.

Current known state:
- `research/PR_REVIEW_STATUS.md` says `completed_yellow`.
- Local/offline gates were green in the previous Codex check.
- Hosted Agentverse/mailbox proof and real-value/testnet payment steps remain operator-owned unless valid process-local secrets and explicit payment approval are supplied.
- This pass must turn that into a precise final agreement state, not vague optimism.

Authority:
- You may edit this standalone repo as needed: `src/**`, `tests/**`, `examples/**`, `docs/**`, `research/**`, `README.md`, project config, and scripts.
- Do not edit `C:\Users\ptann\OneDrive\Work\hermes-agent-main`; read it only for upstream style/source reference.
- Do not inspect `.env`.
- Do not ask for, print, store, or commit seeds, private signing material, recovery phrases, mailbox keys, API tokens, or wallet secrets.
- Do not move real FET, deploy to production, make mainnet transactions, or call hosted Agentverse/ASI paths unless the operator explicitly provides process-local credentials and separately approves that exact step.
- No OpenClaw content and no private legal-tech content in public artifacts.

Required agreement artifacts:
- `research/HERMES_CODEX_DONE_STATUS.md`
- `research/HERMES_CODEX_DONE_AGREEMENT.md`
- `research/OPERATOR_ACTIONS_TO_FINISH.md` if any operator-owned hosted/account/payment steps remain.
- Update `research/PR_REVIEW_STATUS.md`, `research/PR_REVIEW_REPORT.md`, and `research/agentic-economy-research-company/run-state.txt` so they do not contradict the final agreement state.
- Update docs only if the final review finds contradictions, overclaims, missing operator gates, or missing proof instructions.

Required review:
1. Read the current status files:
   - `research/PR_REVIEW_STATUS.md`
   - `research/PR_REVIEW_REPORT.md`
   - `research/agentic-economy-research-company/run-state.txt`
   - `research/FULL_HOOKUP_STATUS.md`
   - `research/FINAL_BOSS_STATUS.md`
   - `research/NORMAL_HERMES_SECRET_TEST_STATUS.md`
2. Read the implementation and tests enough to verify the claims:
   - `src/hermes_fetch_ai/`
   - `tests/`
   - `examples/agentverse-mailbox-hermes.yaml`
   - `examples/payment-dry-run.yaml`
3. Read public docs:
   - `docs/fetch-uagents-bridge.md`
   - `docs/agentverse-hosted-proof.md`
   - `docs/payment-rails.md`
   - `docs/agentic-economy-thesis.md`
4. Reconcile all docs/status files into one honest state.

Required verification commands:
Run and capture exact outcomes:
- `git status --short --branch`
- `git diff --stat`
- `.venv\Scripts\python.exe -m pytest -q`
- `ruff check .`
- `python -m mypy src\hermes_fetch_ai --ignore-missing-imports`
- `.venv\Scripts\python.exe -m hermes_fetch_ai.cli doctor --config examples\agentverse-mailbox-hermes.yaml --probe-backend`
- `.venv\Scripts\python.exe -m hermes_fetch_ai.cli demo local`
- `.venv\Scripts\python.exe -m hermes_fetch_ai.cli demo payment --config examples\payment-dry-run.yaml`
- `.venv\Scripts\python.exe -m hermes_fetch_ai.cli doctor --config examples\agentverse-mailbox-hermes.yaml --contamination-scan`
- Run mailbox demo with no `UAGENT_SEED`; it must fail closed.

Done criteria:
Use exactly one final status in `research/HERMES_CODEX_DONE_STATUS.md`:
- `DONE_AGREED`: all local gates pass, docs are coherent, hosted/payment claims are not overclaimed, and no repo-local blockers remain.
- `BLOCKED_OPERATOR_ONLY`: local gates pass or have no repo-local blocker, but live hosted Agentverse/mailbox or testnet/real-value payment proof requires exact operator-owned account/secret/payment actions. Include exact steps in `research/OPERATOR_ACTIONS_TO_FINISH.md`.
- `BLOCKED_REPO_LOCAL`: a local code/test/docs issue remains. Include file paths, failing commands, and the smallest fix plan.
- `BLOCKED_BY_CHATGPT_QUOTA`: gpt-5.5 quota is exhausted.

Important:
- Do not write `DONE_AGREED` if hosted proof or real-value payment proof is implied but not actually run. In that case use `BLOCKED_OPERATOR_ONLY` and make the required operator steps exact.
- If you can fix repo-local defects safely, fix them and rerun the relevant gates.
- Final log must include exact command outcomes and the final status.
