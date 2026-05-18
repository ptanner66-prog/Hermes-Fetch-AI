You are Hermes, running the final autonomous build pass for Hermes Fetch AI.

Working directory:
C:\Users\ptann\OneDrive\Work\Hermes Fetch AI

Related Hermes upstream checkout:
C:\Users\ptann\OneDrive\Work\hermes-agent-main

This is the high-stakes pass. Codex has done useful draft work, but you are better suited to finish the Hermes-native version. Treat every existing file as a draft that must earn its way into the final repo. Your job is to finish the standalone proof and reduce it into a simplified, maintainer-native upstream PR plan that can credibly go to Teknium/Nous within the next week.

End goal:
Hermes should connect natively to Fetch.ai/uAgents/Agentverse so Hermes can participate in the agentic economy: agent identity, discovery, addressing, messaging, paid work negotiation, and safe execution. The standalone repo is the proving ground. The upstream Hermes PR must be much smaller, cleaner, and native to Hermes conventions.

Core philosophy:
- Connection project, not reinvention.
- Fetch supplies uAgent identity, signed addressing, discovery, Almanac/Agentverse, mailbox/proxy/endpoint delivery, protocols, and payment negotiation rails.
- Hermes supplies local agent intelligence, MCP, tools, safety boundaries, config, logging, plugins, and operator control.
- This repo supplies the thinnest reliable bridge, policy, audit, examples, tests, and upstream translation.
- Do not build a new agent framework.
- Do not bypass existing Fetch/uAgents/Hermes rails unless source evidence proves they are insufficient.
- Do not include legal-tech/private-project content.
- Do not include OpenClaw architecture, examples, or migration content.

Current state you inherit:
- Branch: codex/full-hookup-proof.
- Fake local uAgents dispatcher demo passes.
- Real Hermes stdio MCP proof passes when `HERMES_FETCH_HERMES_PYTHON` points to `C:\Users\ptann\OneDrive\Work\hermes-agent-main\.venv\Scripts\python.exe`.
- `hermes mcp serve` is the actual Hermes seam in this checkout.
- `agent.transports.hermes_tools_mcp_server` is not a valid seam for this checkout.
- A previous Hermes run started adding mailbox startup support in `src/hermes_fetch_ai/cli.py`, `src/hermes_fetch_ai/uagent_app.py`, and `examples/agentverse-mailbox-hermes.yaml`. Keep, fix, or replace it only after tests prove the result.

Read first:
- `AGENTS.md` if present in this repo.
- `research/FULL_HOOKUP_STATUS.md`
- `research/FINAL_ARCHITECTURE_DECISION.md`
- `research/FULL_HOOKUP_PROOF_PROMPT.md`
- `research/FETCH_ACCOUNT_REQUIREMENTS.md`
- `README.md`
- `docs/`
- `src/hermes_fetch_ai/`
- `tests/`
- `C:\Users\ptann\OneDrive\Work\hermes-agent-main\AGENTS.md`
- `C:\Users\ptann\OneDrive\Work\hermes-agent-main\mcp_serve.py`
- `C:\Users\ptann\OneDrive\Work\hermes-agent-main\tests\test_mcp_serve.py`
- Hermes plugin/CLI docs and code paths called out in the Hermes AGENTS.md.
- If present, read `research/FULL_CONNECTION_FETCH_WEBSITE_ADDENDUM.md`, `research/FULL_CONNECTION_ALMANAC_ADDENDUM.md`, and `research/FULL_CONNECTION_A2A_AGENTVERSE_ADDENDUM.md`; they supersede any narrower mailbox-only interpretation of the goal.

Use web and GitHub/source research. This is mandatory.

Current source anchors to verify, not blindly trust:
- Hermes MCP docs: https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp/
- Fetch/uAgents mailbox/types docs: https://uagents.fetch.ai/docs/guides/types
- Fetch/uAgents payment protocol docs: https://uagents.fetch.ai/docs/guides/agent-payment-protocol
- Fetch.ai website and developer platform: https://www.fetch.ai/ and https://fetch.ai/docs/concepts
- Fetch Agentverse product page: https://www.fetch.ai/agentverse
- Fetch Network / Almanac docs: https://network.fetch.ai/docs and https://network.fetch.ai/docs/introduction/almanac/introduction
- Agentverse external A2A launch docs: https://docs.agentverse.ai/documentation/launch-agents/external-agents/a-2-a-agents
- Agentverse Almanac manifest APIs: https://docs.agentverse.ai/api-reference/almanac/get-manifest and related manifest upload/name/model endpoints
- Fetch/uAgents GitHub source: https://github.com/fetchai/uAgents
- Hermes upstream repo and PRs: https://github.com/NousResearch/hermes-agent

If your web/GitHub tools fail:
1. Diagnose why.
2. Use `gh` if available.
3. Use GitHub REST endpoints or `git fetch upstream main` as fallback.
4. Record the fallback in `research/SOURCE_ACCESS_LOG.md`.
5. Do not proceed to final acceptance without source-backed claims.

PR-style research requirement:
Create `research/NOUS_HERMES_PR_STYLE_REVIEW.md`.

Inspect at least 15 recent merged or maintainer-endorsed NousResearch/hermes-agent PRs, prioritizing plugin, CLI, gateway/platform, MCP, optional dependency, config, and docs PRs. Use one or more of:
- `gh pr list -R NousResearch/hermes-agent --state merged --limit 50 --json number,title,url,mergedAt,additions,deletions,changedFiles,labels,author`
- GitHub REST API for closed PRs filtered by `merged_at`.
- Local `git -C C:\Users\ptann\OneDrive\Work\hermes-agent-main log` and merge commits from `upstream/main`.

Extract maintainer style:
- PR size and file-count patterns.
- Where optional integrations live.
- How tests are shaped.
- How docs and config are added.
- How plugin surfaces are preferred over core changes.
- What not to touch.
- How to phrase the final PR description for Teknium.

Then clean this repo to match those lessons:
- No scaffolding feel.
- No stale contradictions saying payment/agentic-economy work is out of scope.
- No overbroad upstream plan.
- No fake completion claims.
- No brittle demos.
- No unbounded or secret-printing logs.
- No side-effecting Hermes tools exposed by default.

Full hookup requirements:
1. Keep fake local demo green.
2. Keep real Hermes stdio MCP demo green.
3. Keep `doctor --probe-backend` clear and useful.
4. Implement or harden a mailbox proof path that starts the bridge in mailbox mode without printing secrets.
5. Produce `research/HOSTED_DEMO_BLOCKER.md` if real hosted Agentverse account/linking is still required. It must contain exact operator steps and nothing vague.
6. If an operator provides the needed Agentverse account/seed/mailbox setup later, the repo should already have the exact command path to prove:
   remote uAgent -> Agentverse/Mailbox/endpoint -> Hermes Fetch AI -> Hermes `mcp serve` -> response.
7. If hosted proof can be performed without operator secrets, perform it and record evidence in `research/HOSTED_HOOKUP_EVIDENCE.md`.

Payment / agentic economy requirement:
This is no longer "just mailbox". Add the safest production-shaped payment infrastructure the current Fetch rails support.

Mandatory research:
- Verify the current `uagents_core.contrib.protocols.payment` API and payment protocol docs/source.
- Verify available payment methods and current examples such as `fet_direct`, `skyfire`, FET, and USDC.
- Verify what requires real wallet/account/FET and what can be tested locally.
- Record results in `research/PAYMENT_RAILS_RESEARCH.md` with source links and exact package/source references.

Mandatory implementation shape:
- Payment support must be optional and disabled by default.
- No real FET spend, mainnet transaction, private key handling, seed printing, mailbox key printing, recovery phrase handling, or production deployment without an explicit operator stop.
- Build dry-run/testnet-first rails:
  - config section for payment mode: disabled, dry_run, testnet, real_operator_approved.
  - accepted funds / method configuration.
  - priced tool policy or paid action policy.
  - idempotency/reference model.
  - audit events for request, commit, complete, cancel, reject.
  - local in-process uAgents payment protocol tests using official message models if available.
  - a demo that proves the negotiation path without moving funds.
- The bridge must treat Agentverse/uAgent identity as routing identity, not trust.
- Payment commitment must never automatically authorize dangerous Hermes tools.
- Side-effecting Hermes tools remain denied by default unless an explicit policy says otherwise.
- If real hosted/FET setup is needed, write `research/PAYMENT_OPERATOR_ACTIONS.md` with exact steps and stop. Do not request or store secrets. Do not spend or deploy FET.

Possible implementation target, subject to source verification:
- Import official payment protocol symbols from `uagents_core.contrib.protocols.payment` if present and stable enough.
- Add a small `payments.py` / `payment_policy.py` / tests layer that composes with the existing direct protocol.
- If official symbols are unavailable or incompatible, vendor only minimal message models with attribution and explain why in `research/PAYMENT_RAILS_RESEARCH.md`.
- Add `hermes-fetch-ai demo payment-dry-run` or equivalent.
- Add tests that fail if real network/wallet calls are made in CI.

Upstream Hermes PR requirement:
Create `research/UPSTREAM_PR_EXECUTION_PLAN.md` or update it if present.

The upstream PR should be simplified and Hermes-native:
- Prefer a Hermes plugin or `hermes uagents serve` command if current Hermes plugin/CLI patterns support it.
- Avoid copying the standalone repo wholesale.
- Avoid gateway `BasePlatformAdapter` unless source evidence shows uAgent RPC belongs in the gateway platform layer.
- Optional dependency strategy must follow Hermes conventions.
- Config must respect Hermes profile rules: use `get_hermes_home()` and `display_hermes_home()` in Hermes code.
- Plugin code must not modify core files unless the generic plugin surface must be expanded.
- Include exact files to touch, tests to add, and docs to add in `hermes-agent-main`.
- Include a PR description that says plainly: Hermes remains the local execution agent; Fetch/uAgents supplies identity, discovery, transport, mailbox, and payment protocol rails.

Do not open an upstream PR in this run unless explicitly instructed by the operator. If you create an upstream branch locally, keep it narrow and record it in the research file.

Verification commands for this repo:
```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy src\hermes_fetch_ai --ignore-missing-imports
.\.venv\Scripts\python.exe -m hermes_fetch_ai.cli doctor --contamination-scan
$env:HERMES_FETCH_HERMES_PYTHON='C:\Users\ptann\OneDrive\Work\hermes-agent-main\.venv\Scripts\python.exe'
.\.venv\Scripts\python.exe -m hermes_fetch_ai.cli doctor --config examples\hermes-stdio-env.yaml --probe-backend
.\.venv\Scripts\python.exe -m hermes_fetch_ai.cli demo hermes --config examples\hermes-stdio-env.yaml
```

Add equivalent commands for:
- mailbox startup proof or hosted blocker validation.
- payment dry-run demo.
- payment policy tests.
- upstream PR plan validation.

Old contamination policy warning:
Earlier docs intentionally excluded payment/marketplace work. The operator has changed scope. Update docs/tests/scans so payment protocol infrastructure is allowed when it is safe, optional, default-off, source-backed, and not a marketplace sprawl. Continue banning OpenClaw, legal-tech/private content, secrets, real private keys, real FET movement, and fake claims.

Final acceptance:
Do not stop until one of these is true:

GO:
- fake local tests pass.
- real Hermes stdio proof passes.
- mailbox hosted path is either proven or blocked only by exact operator account/seed/linking steps.
- payment dry-run/testnet infrastructure is implemented, tested, default-off, and documented.
- no real FET has been moved.
- `research/PAYMENT_OPERATOR_ACTIONS.md` exists if any real account/wallet/FET step is needed.
- source-backed PR-style research exists.
- upstream Hermes PR execution plan is narrow and realistic.
- code is cleaned after PR-style review.
- docs no longer contradict the agentic-economy goal.
- all verification commands pass.
- commit is created locally.
- push is attempted only if safe; if push is blocked by the local environment, record exact reason.

NO-GO:
- any required source access cannot be restored.
- local tests cannot be made green.
- payment rails would require handling secrets or moving FET to continue.
- hosted demo is blocked by operator action and the exact next step is documented.

Write final status to `research/FINAL_BOSS_STATUS.md`.

Final output must include:
- exact files changed.
- exact tests/commands run.
- what is proven.
- what remains operator-owned.
- whether Porter needs to create a Fetch/Agentverse account now.
- whether any FET is needed now.
- local commit SHA.
- branch and push state.
- one-line Teknium-facing summary.
