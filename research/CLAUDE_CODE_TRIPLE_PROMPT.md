# Claude Code Triple Prompt

Use these as three separate Claude Code runs after the GitHub PR is open. Keep all three in the Hermes Fetch AI repo root.

Global constraints for every run:

- Do not inspect `.env` or ask the operator to paste secrets.
- Do not print, store, commit, or transmit `UAGENT_SEED`, Agentverse API credentials, mailbox credentials, wallet signing material, payment processor secrets, or generated registration scripts.
- Do not call hosted Agentverse/ASI, move FET, run testnet/mainnet, deploy to production, force-push, or merge without explicit current-context operator approval.
- Treat legal/compliance review as operator-risk review, not legal advice.
- Preserve the architecture: Hermes is the local runtime; Fetch/uAgents/Agentverse/Almanac are identity, discovery, addressing, mailbox/proxy, protocol, A2A, manifest, wallet/network, and payment rails.
- The bridge should stay the thinnest reliable connector, not a new agent framework.

## Prompt 1: Security And Fail-Closed Review

You are Claude Code running a security and fail-closed review of Hermes Fetch AI.

Goal: independently verify that the PR is safe for the operator to sign into Agentverse and run mailbox/Inspector proof without exposing secrets or broad Hermes tools.

Read first:

- `docs/agentverse-operator-handoff.md`
- `research/AGENTVERSE_TAKEOVER_READINESS_REVIEW.md`
- `research/OPERATOR_ACTIONS_TO_FINISH.md`
- `src/hermes_fetch_ai/direct_protocol.py`
- `src/hermes_fetch_ai/config.py`
- `src/hermes_fetch_ai/mcp_shim.py`
- `src/hermes_fetch_ai/uagent_app.py`
- `tests/test_direct_protocol_policy.py`
- `tests/test_mailbox_startup.py`

Tasks:

1. Verify `ListTools` with empty public policy and no sender allowlist does not contact Hermes/MCP backend.
2. Verify backend exceptions and tool errors cannot leak raw backend text to remote callers.
3. Verify `demo hermes` exits nonzero on bridged tool errors.
4. Verify mailbox/proxy mode requires process-local `UAGENT_SEED` and rejects YAML/direct identity secrets.
5. Verify contamination scan covers public docs, examples, README, and source.
6. Run targeted tests and report exact commands and results.

Acceptance:

- If repo-local issues remain, patch them and add tests.
- If only operator-owned hosted proof remains, leave code unchanged and write a concise report.
- Do not make hosted calls or inspect secrets.

## Prompt 2: Agentverse Operator Runbook Review

You are Claude Code running an Agentverse operations readiness review.

Goal: make the operator handoff precise enough that the operator can sign in, link mailbox/Inspector, start the real Hermes bridge, and capture sanitized evidence without guessing.

Read first:

- `docs/agentverse-operator-handoff.md`
- `docs/agentverse-hosted-proof.md`
- `docs/demo.md`
- `examples/README.md`
- `examples/agentverse-mailbox.yaml`
- `examples/agentverse-mailbox-hermes.yaml`
- `research/HOSTED_HOOKUP_EVIDENCE.md`
- `research/OPERATOR_ACTIONS_TO_FINISH.md`

Official docs to verify:

- `https://docs.agentverse.ai/documentation/launch-agents/external-agents/u-agents`
- `https://docs.agentverse.ai/api-reference/agents/submit-mailbox-message`
- `https://docs.agentverse.ai/documentation/advanced-usages/agent-logs-errors`
- `https://uagents.fetch.ai/docs/guides/agent-payment-protocol`

Tasks:

1. Confirm the first live proof path is mailbox/Inspector, not external ACP registration.
2. Confirm `agentverse-mailbox.yaml` is clearly first-linking only and fake-MCP-backed.
3. Confirm `agentverse-mailbox-hermes.yaml` is the real Hermes bridge config and keeps public tools empty.
4. Confirm `HOSTED_HOOKUP_EVIDENCE.md` gives the operator exact fields for command results, remote transcript, stop conditions, and final verdict.
5. Remove machine-specific public paths from docs if any remain.
6. Make payment wording explicit: CLI dry-run protocol-model proof only until separate operator approval.

Acceptance:

- If runbook ambiguity remains, patch docs only.
- Do not run hosted Agentverse flows.
- Do not broaden public tool exposure.

## Prompt 3: PR Package And Merge-Readiness Review

You are Claude Code running a PR package review for Hermes Fetch AI.

Goal: verify the PR is coherent, reviewable, and honest about what is done versus operator-owned.

Read first:

- `README.md`
- `research/PR_REVIEW_STATUS.md`
- `research/PR_REVIEW_REPORT.md`
- `research/UPSTREAM_PR_DESCRIPTION.md`
- `research/UPSTREAM_PR_REVIEW_CHECKLIST.md`
- `research/HERMES_OVERNIGHT_UNTIL_DONE_STATUS.md`
- `research/AGENTVERSE_TAKEOVER_READINESS_REVIEW.md`

Tasks:

1. Compare PR docs against implementation and tests.
2. Verify no document claims `DONE_AGREED`, hosted Agentverse proof, remote payment negotiation, or settlement unless evidence exists.
3. Verify the current local validation matrix is up to date.
4. Verify dirty-tree/package contents are intentional and do not include logs, caches, `.env`, or secret material.
5. Run final local gates if dependencies are present:
   - `python -m pytest -q`
   - `python -m ruff check .`
   - `python -m mypy src`
   - `python -m hermes_fetch_ai.cli doctor --contamination-scan`
6. Produce a short PR-review report with findings first, then residual operator actions.

Acceptance:

- Patch doc/status drift if found.
- Do not merge.
- Do not mark ready beyond `BLOCKED_OPERATOR_ONLY` until hosted evidence exists or the operator explicitly accepts the hold.
