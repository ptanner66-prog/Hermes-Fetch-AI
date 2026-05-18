You are continuing the Hermes Fetch AI max-reasoning MOE hardening run.

Working directory:
C:\Users\ptann\OneDrive\Work\Hermes Fetch AI

Hard route requirement:
- ChatGPT-only: model gpt-5.5, provider openai-codex, api_mode codex_responses.
- Do not route to Nous, OpenRouter, Anthropic, Claude, or any non-ChatGPT provider.
- fallback_providers must remain [].
- Start at reasoning_effort=xhigh. If the local Hermes agent loop lowers reasoning on a ChatGPT rate/usage limit, record the effective reasoning path honestly.

Context:
- The previous MOE run exited with code 0 but did not meet acceptance.
- It produced useful notes in research/moe-hardening-run.log and a partial research/MOE_HARDENING_STATUS.md.
- Continue from that state. Do not restart from scratch. Do not overwrite useful findings unless correcting them.

Primary mission:
Make the repo genuinely Teknium-facing within the ChatGPT-only constraint. This is a connection project, not a reinvention project. Fetch/uAgents/Agentverse/Almanac/A2A/payment rails provide identity, discovery, addressing, delivery, protocol manifests, wallet/network context, and payment negotiation. Hermes provides local intelligence, MCP, tools, safety, config, logging, plugins, and operator boundaries. The repo should be the thinnest reliable bridge.

Required outputs before stopping:
- research/MOE_HARDENING_STATUS.md
- research/MOE_HARDENING_REPORT.md
- research/FETCH_GITHUB_SWEEP.md
- research/HERMES_UPSTREAM_SWEEP.md
- research/FULL_CONNECTION_GAP_AUDIT.md
- research/TEKNIUM_PR_ONE_PAGER.md
- research/FINAL_BOSS_STATUS.md
- Update research/UPSTREAM_PR_EXECUTION_PLAN.md if the MOE pass changes the PR shape.

Required verification before final status:
- .\.venv\Scripts\python.exe -m pytest -q
- .\.venv\Scripts\python.exe -m ruff check .
- .\.venv\Scripts\python.exe -m mypy src\hermes_fetch_ai --ignore-missing-imports
- .\.venv\Scripts\python.exe -m hermes_fetch_ai.cli doctor --contamination-scan
- Hermes stdio backend probe
- Hermes local demo
- payment dry-run demo/tests
- mailbox proof or explicit hosted/operator blocker validation

If a verification failure is agent-solvable, fix it. If it is operator-owned, document the exact blocker. Do not claim green with stale or partial evidence.

Guardrails:
- Do not inspect, print, store, or commit .env values, UAGENT_SEED, wallet secrets, private keys, recovery phrases, mailbox keys, or API secrets.
- No real FET movement, no mainnet transaction, no production deploy.
- No legal-tech/private project content and no OpenClaw content.
- No force-push, no amend of pushed commits, no --no-verify.
- Do not commit research/repos, research/pkgs, research/public, logs, .venv, node_modules, or temp files.

When done, write an honest final status with:
- exact model/provider/api_mode/reasoning path used,
- exact verification command results,
- exact remaining blockers, if any,
- final commit/push state, if any.
