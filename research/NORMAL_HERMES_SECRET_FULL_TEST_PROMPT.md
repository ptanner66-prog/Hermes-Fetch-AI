You are continuing the Hermes Fetch AI project in operator-secret full-test mode.

Working directory:
C:\Users\ptann\OneDrive\Work\Hermes Fetch AI

Hermes source checkout:
C:\Users\ptann\OneDrive\Work\hermes-agent-main

Route constraint:
- ChatGPT-only: model gpt-5.5, provider openai-codex, api_mode codex_responses.
- Do not switch to another model unless the operator explicitly says to switch.
- Do not route to Nous, OpenRouter, Anthropic, Claude, or any non-ChatGPT provider.
- Start with reasoning_effort=xhigh. If the local Hermes runtime lowers reasoning on the same ChatGPT provider/model after a rate/usage limit, record the effective path honestly.

Mission:
Turn the current standalone proof into a real normal-Hermes hosted-test path without ever leaking operator secrets. The user is willing to log into Fetch/Agentverse and may fund a small test allocation, but you must keep all seeds, mailbox keys, wallet material, recovery phrases, API keys, and private credentials operator-owned.

Core philosophy:
This is a connection project, not a reinvention project. Fetch/uAgents/Agentverse/Almanac supply identity, discovery, addressing, endpoint/mailbox/proxy delivery, protocols, A2A launch surfaces, manifests, wallet/network context, and payment negotiation. Hermes supplies local intelligence, MCP, tools, safety, config, logging, plugins, and operator boundaries. The bridge should be the thinnest reliable connection.

Hard safety rules:
- Never ask the user to paste a seed phrase, private key, recovery phrase, mailbox key, wallet secret, API key, or `.env` value into chat or any committed file.
- Do not inspect `.env`.
- Do not print, echo, log, commit, or persist `UAGENT_SEED`, wallet keys, Agentverse tokens, mailbox keys, API keys, or recovery phrases.
- Do not create a repo-local secret file.
- Prefer process-local environment variables entered by the operator at runtime. If a persistent secret store is unavoidable, document it as an operator-owned choice and keep it outside this repo.
- No real FET movement, mainnet transaction, payment settlement, hosted action with real value, production deploy, or public registration using operator identity without a separate explicit operator approval after local gates are green.
- No legal-tech/private project content and no OpenClaw content.
- Treat Agentverse/uAgent identity as identity, not trust.

Operator-secret model:
- You may prepare commands and scripts that prompt the operator locally.
- You may run no-secret checks immediately.
- You may run hosted mailbox proof only if required secrets already exist in this process environment and the operator explicitly requested that run.
- You may run payment dry-run immediately.
- You must stop before any real FET transfer/settlement and write exact next approval text needed from the operator.

Normal Hermes target:
- Use the real local Hermes checkout at `C:\Users\ptann\OneDrive\Work\hermes-agent-main`.
- Use `HERMES_FETCH_HERMES_PYTHON` pointing to its `.venv\Scripts\python.exe` when available.
- Validate the Hermes MCP backend through `examples\agentverse-mailbox-hermes.yaml`.
- Keep side-effecting Hermes MCP tools denied unless explicitly allowlisted per sender.

Required source review:
Use existing research, local source, and current web/GitHub docs if available. At minimum verify the current shape of:
- Fetch/Agentverse external uAgents launch docs.
- Fetch/Agentverse external A2A launch docs.
- uAgents mailbox/proxy/endpoint behavior.
- Almanac manifest APIs and protocol/model digest expectations.
- Agentverse subscriptions/quotas.
- Fetch/uAgents and fetchai/api-clients GitHub source where relevant.
- NousResearch/hermes-agent source and PR style where relevant.

Required local commands, when safe:
Run and record exact outcomes:
- `.venv\Scripts\python.exe -m pytest -q`
- `ruff check .`
- `mypy src\hermes_fetch_ai --ignore-missing-imports`
- `.venv\Scripts\python.exe -m hermes_fetch_ai.cli doctor --config examples\agentverse-mailbox-hermes.yaml --probe-backend`
- `.venv\Scripts\python.exe -m hermes_fetch_ai.cli demo local`
- `.venv\Scripts\python.exe -m hermes_fetch_ai.cli demo payment --config examples\payment-dry-run.yaml`
- `.venv\Scripts\python.exe -m hermes_fetch_ai.cli doctor --config examples\agentverse-mailbox-hermes.yaml --contamination-scan`
- Mailbox startup without `UAGENT_SEED` must fail closed; record this as a safety pass, not a hosted proof.

If operator secrets are not present:
- Do not mark hosted proof complete.
- Write the exact operator runbook and set status to `WAITING_FOR_OPERATOR_SECRETS`.

If operator secrets are present:
- Confirm they are only detected as present/absent; never print values.
- Run the shortest hosted mailbox proof that demonstrates the bridge can start with normal Hermes MCP and fail safely on policy-denied public tools.
- Keep the run bounded by a duration.
- Capture only redacted logs and non-secret evidence.
- If hosted Agentverse browser linking is required, stop and document the browser steps instead of attempting to scrape or store credentials.

Required outputs:
1. `research/NORMAL_HERMES_SECRET_TEST_RUNBOOK.md`
   - Exact Windows PowerShell steps for Porter.
   - Distinguish browser steps, local terminal steps, and what Hermes/Codex can verify.
   - Include a secure process-local prompt pattern for `UAGENT_SEED`, not inline shell-history assignment.
   - Include how to set `HERMES_FETCH_HERMES_PYTHON`.
   - Include the exact commands to run after secrets are entered.
   - Include a stop point before any real FET movement.

2. `research/NORMAL_HERMES_SECRET_TEST_STATUS.md`
   - Runtime model/provider/api_mode/effective reasoning path.
   - Commands run and results.
   - Whether hosted mailbox proof was actually run.
   - Whether any account/login/FET action remains operator-owned.
   - Explicit statement that no secrets were printed/stored/committed.

3. `research/FET_TEST_FUNDS_PLAN.md`
   - Current recommendation for minimum viable real-value test, if any.
   - Separate dry-run, testnet/sandbox, and mainnet/real-value settlement.
   - Preconditions before asking for explicit FET approval.
   - A precise approval sentence Porter must send before any real value movement.

4. Update `research/HOSTED_DEMO_BLOCKER.md` and `research/PAYMENT_OPERATOR_ACTIONS.md`
   - Make them current, precise, and operator-actionable.
   - Do not overstate hosted proof if secrets/browser login are still pending.

5. If you identify code gaps that prevent the normal-Hermes hosted proof, fix them narrowly and add tests.
   - Do not add broad new framework code.
   - Keep payment rails disabled by default and dry-run/testnet safe.
   - Never commit secrets or logs.

Final status rules:
- `GREEN_LOCAL_WAITING_FOR_OPERATOR` is acceptable only if all local gates pass and the only remaining steps are exact operator-owned login/secret/FET actions.
- `GREEN_HOSTED_NO_VALUE_MOVED` is acceptable only if hosted mailbox proof ran with operator-provided environment secrets and no real FET moved.
- `GREEN_PAYMENT_DRY_RUN_ONLY` is acceptable for payment until a separate explicit real-FET approval is provided.
- Any real FET transfer/settlement requires a separate explicit approval after you write the amount, network, address/recipient category, command, and risk.

Stop condition:
Stop when the repo has a precise normal-Hermes secret-test runbook, current status, updated hosted/payment operator action docs, all no-secret local gates recorded, and hosted/payment status is honest. If real hosted/FET execution requires operator action, stop cleanly and request only the exact operator-owned action without asking for secrets in chat.
