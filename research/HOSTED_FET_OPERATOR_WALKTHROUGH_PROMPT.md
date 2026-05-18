You are continuing the Hermes Fetch AI project after the local/MOE hardening pass.

Working directory:
C:\Users\ptann\OneDrive\Work\Hermes Fetch AI

Route constraint:
- ChatGPT-only: model gpt-5.5, provider openai-codex, api_mode codex_responses.
- Do not route to Nous, OpenRouter, Anthropic, Claude, or any non-ChatGPT provider.
- Start from reasoning_effort=xhigh. If the local Hermes runtime lowers reasoning after a same-provider ChatGPT rate/usage limit, record that honestly.

Mission:
Prepare the operator-assisted hosted Fetch/Agentverse/FET walkthrough. The user is willing to create/log into the required Fetch/Agentverse account and may fund up to some FET for testing, but you must keep all secrets and real value movement operator-owned.

Hard safety rules:
- Never ask the user to paste a seed phrase, private key, recovery phrase, mailbox key, wallet secret, API key, or .env value into chat or into any file.
- Do not inspect .env.
- Do not print or store UAGENT_SEED.
- No real FET movement, mainnet transaction, payment settlement, hosted action, or production deploy without a separate explicit operator approval after the local gates are green.
- Treat Agentverse/uAgent identity as identity, not trust.
- No legal-tech/private project content and no OpenClaw content.

Source requirements:
Use the existing repo research, then verify current official docs with web/GitHub/source access if available. At minimum consider:
- https://docs.agentverse.ai/documentation/launch-agents/external-agents/u-agents
- https://docs.agentverse.ai/documentation/launch-agents/external-agents/a-2-a-agents
- https://uagents.fetch.ai/docs/agentverse/mailbox
- https://docs.agentverse.ai/documentation/advanced-usages/agentverse-subscriptions-and-quotas
- https://docs.agentverse.ai/api-reference/almanac/get-manifest
- https://github.com/fetchai/uAgents
- https://github.com/fetchai/api-clients

Required outputs:
1. `research/HOSTED_OPERATOR_WALKTHROUGH.md`
   - A step-by-step walkthrough for Porter to create/log into Agentverse, set up any required account/API key/mailbox/seed locally, and run the hosted mailbox/Agentverse proof.
   - Must clearly distinguish what Porter does in browser, what Porter runs in terminal, and what Hermes/Codex can verify after the fact.
   - Must say exactly where secrets live: operator shell/environment only; never chat, never committed files.
   - Must include exact commands for this repo using Windows PowerShell syntax.
   - Must include the stopping point before any real FET spend.

2. `research/FET_TEST_FUNDS_PLAN.md`
   - Explain whether any FET is required for the next proof.
   - Separate dry-run, testnet/sandbox if available, and real-value/mainnet settlement.
   - If real FET is needed, specify the minimum viable test amount and exact preconditions before asking for explicit approval.
   - No transaction is to be initiated by you.

3. Update `research/HOSTED_DEMO_BLOCKER.md` and `research/PAYMENT_OPERATOR_ACTIONS.md`
   - Make them current, precise, and operator-actionable.
   - Keep hosted mailbox and payment settlement blockers honest.

4. `research/HOSTED_FET_WALKTHROUGH_STATUS.md`
   - Record model/provider/api_mode/reasoning path, source links consulted, files changed, commands run, and remaining operator actions.

5. If a command can be safely run locally without secrets, run it and record exact result.
   - Safe examples: doctor without UAGENT_SEED should fail closed; payment dry-run should pass.
   - Do not run hosted mailbox with a real seed unless the operator has already set it in the shell and explicitly asked you to proceed.

Expected philosophy:
This is a connection project, not a reinvention project. The hosted proof should validate existing Fetch/Agentverse/uAgents rails around the Hermes bridge, not invent a new payment or identity system.

Stop condition:
Stop when the operator walkthrough is precise enough for Porter to follow, local no-secret checks are recorded, and all real account/FET actions are explicitly separated as operator-owned.
