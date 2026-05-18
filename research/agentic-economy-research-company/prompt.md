# Agentic Economy Research Company Run Prompt

Run date: 2026-05-17
Runtime route: ChatGPT-only; model gpt-5.5; provider openai-codex; API mode codex_responses. Non-ChatGPT fallback forbidden. If gpt-5.5 quota is exhausted, stop and record BLOCKED_BY_CHATGPT_QUOTA.

Target repository: C:\Users\ptann\OneDrive\Work\Hermes Fetch AI
Hermes repository: C:\Users\ptann\OneDrive\Work\hermes-agent-main

Mission: produce source-backed, implementation-ready research, docs, and PR review artifacts showing how Hermes can use Fetch.ai/uAgents/Agentverse/Almanac rails as a thin, safe, testable bridge into the agentic economy.

Patch authority: docs/research/README only. No implementation, tests, examples, pyproject, CI, or Hermes source edits in this run.

Binding pre-read sources:
- C:\Users\ptann\OneDrive\Work\hermes-agent-main\codex\PROMPTING_GUIDE.md
- C:\Users\ptann\OneDrive\Work\hermes-agent-main\docs\hermes-reviewer-prompting.md
- C:\Users\ptann\OneDrive\Work\hermes-agent-main\OPERATOR-INBOX\clay\HERMES-LEASH-PROMPT-TEMPLATE.md

Four-axis frame:
- Target: target repo docs/research/README artifacts plus evidence from target repo, local Hermes repo, and official Fetch sources.
- Risk: overclaiming, stale source evidence, unsafe payment/hosted claims, false-green tests, scope creep, secret exposure, implementation/test defects hidden by docs.
- Authority: operator prompt, binding Hermes prompting docs above, target repo filesystem, official Fetch/Agentverse/uAgents docs and fetchai GitHub source, local Hermes repo source when used.
- Verdict: GO / GO WITH WARNINGS / NO-GO / BLOCKED mapped to run-state completed_green/completed_yellow/completed_red/blocked_* with evidence.

Guardrails:
- Do not inspect .env or print secrets.
- No real FET movement, mainnet transaction, production deploy, force-push, or credentialed hosted action.
- Hosted Agentverse/ASI actions requiring credentials are operator-only unless explicitly approved.
- Label unverifiable claims GAP or HYPOTHESIS.
