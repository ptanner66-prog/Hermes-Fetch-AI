# PR Review Report

Status: BLOCKED_OPERATOR_ONLY. Local/offline verification is green after repo-local hardening; hosted Agentverse/mailbox and testnet/real-value payment proofs remain operator-owned and were not run.

## Review scope

This overnight until-done review covers the Hermes Fetch AI bridge as a thin connection between the Hermes local runtime and Fetch/uAgents/Agentverse/Almanac rails.

Authority in this pass:

- May edit this standalone repo as needed: `src/**`, `tests/**`, `examples/**`, `docs/**`, `research/**`, `README.md`, project config, and scripts.
- Must not edit `C:\Users\ptann\OneDrive\Work\hermes-agent-main`; read-only upstream reference is allowed.
- Must not inspect `.env`.
- Must not ask for, print, store, or commit seeds, private signing material, recovery phrases, mailbox keys, API tokens, or wallet secrets.
- Must not move real FET, deploy to production, make mainnet/testnet transactions, or call hosted Agentverse/ASI paths without process-local credentials and separate approval.
- Must not include OpenClaw or private legal-tech content in public artifacts.

## Evidence reviewed

- Prior status files: `research/HERMES_CODEX_DONE_STATUS.md`, `research/HERMES_CODEX_DONE_AGREEMENT.md`, `research/OPERATOR_ACTIONS_TO_FINISH.md`, `research/PR_REVIEW_STATUS.md`, `research/PR_REVIEW_REPORT.md`, and `research/agentic-economy-research-company/run-state.txt`.
- Implementation: `src/hermes_fetch_ai/` including config, CLI, uAgent app, MCP shim, protocol handlers, payment dry-run, policy, validation, audit, redaction, probe, and result normalization.
- Tests: `tests/` including config, mailbox startup, payment, contamination, security defaults, policy, direct protocol, validators, redaction, result normalization, and MCP shim coverage.
- Examples: `examples/agentverse-mailbox-hermes.yaml`, `examples/payment-dry-run.yaml`, plus related local/Hermes stdio configs.
- Public docs: `docs/fetch-uagents-bridge.md`, `docs/agentverse-hosted-proof.md`, `docs/payment-rails.md`, `docs/agentic-economy-thesis.md`, README, and related public run docs.

No `.env` file was inspected.

## Implementation/test issue log

Fixed in this pass:

1. Config accepted or could reuse non-env seed material in ways that undercut the documented fail-closed posture.
   - `agent.seed` and `agent.mailbox_key` are now rejected in config/direct model input.
   - YAML seed values are rejected even when dev-prefixed.
   - Static config loading for doctor/probe can still parse mailbox configs without runtime secrets, but `effective_seed()` still fails closed without non-blank `UAGENT_SEED`.
   - Mailbox/proxy modes reject dev-random identity.
   - Missing/secret-shaped stdio env expansion now fails closed.

2. Payment dry-run safety needed defense-in-depth.
   - `payment.mode=testnet` and `payment.mode=real_operator_approved` are operator stops in this repo-local proof.
   - `PaymentDryRunStore` now rejects non-dry-run configs.
   - Unknown dry-run payment references no longer echo a full transaction-like id.
   - Dry-run commits still require `dryrun-*` ids.

3. Contamination coverage needed to cover the CLI scan path as well as the public-tree test.
   - Public-tree forbidden term coverage was broadened.
   - CLI contamination scan is now exercised by tests.

4. Agentverse takeover review found additional repo-local readiness gaps.
   - Empty visible `ListTools` now returns an empty list without contacting the backend.
   - Backend tool errors and backend exceptions return a generic remote error while audit data remains sanitized.
   - `demo hermes` now exits nonzero when the bridged tool call fails or returns no result.
   - The live handoff now uses mailbox/Inspector first; external ACP registration is deferred until a public ACP endpoint exists.
   - `research/HOSTED_HOOKUP_EVIDENCE.md` provides a fixed evidence template for sanitized operator proof.

## Verification command outcomes

| Command | Exit | Outcome |
|---|---:|---|
| `git status --short --branch` | 0 | Branch `codex/full-hookup-proof`; dirty working tree with tracked implementation/docs/research changes and many untracked docs/research/examples/tests artifacts, including overnight status/report files. |
| `git diff --stat` | 0 | Tracked diff present: 16 files changed, 879 insertions, 318 deletions; warnings only about LF->CRLF normalization. Untracked files are not represented by this command. |
| `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` | 0 | `97 passed in 16.64s`. |
| `ruff check .` | 0 | `All checks passed!`. |
| `python -m mypy src` | 0 | `Success: no issues found in 20 source files`. |
| mailbox Hermes backend probe | 0 | `backend: ok: 10 tools`; `doctor: ok`. |
| `.venv/Scripts/python.exe -m hermes_fetch_ai.cli demo local` | 0 | Local bridge demo succeeded: bridge address printed, visible tool count `1`, `echo result: hello`, audit event count `4`. |
| `.venv/Scripts/python.exe -m hermes_fetch_ai.cli demo hermes --config examples/hermes-stdio-env.yaml` | 0 | Hermes stdio bridge demo succeeded: visible tool count `2`, `conversations_list` returned `{"count": 0, "conversations": []}`, audit event count `4`. |
| `.venv/Scripts/python.exe -m hermes_fetch_ai.cli demo payment --config examples/payment-dry-run.yaml` | 0 | Dry-run payment proof succeeded: request created, accepted `0.01 FET via fet_direct`, commit `complete`, completion `CompletePayment`, audit event count `2`, and `no real funds moved; no wallet secret or FET spend used`. |
| contamination scan | 0 | `contamination: ok`; `doctor: ok`. |
| mailbox demo with no `UAGENT_SEED` | 1 | Expected negative check passed: command failed closed with `UAGENT_SEED is required when agent.dev_random_seed=false`. |

Exact command output is preserved in `research/HERMES_OVERNIGHT_UNTIL_DONE_REPORT.md`.

## Documentation review

- Thesis is consistent: Hermes is runtime; Fetch/uAgents/Agentverse/Almanac are rails.
- Public docs distinguish local proof, hosted/mailbox proof, dry-run payment, testnet/sandbox, and real-value/mainnet proof levels.
- Hosted Agentverse/mailbox proof is documented as not completed by local-only runs.
- Payment docs claim dry-run negotiation only; no settlement, wallet custody, real FET movement, Stripe/Skyfire/FET verification, or marketplace launch is claimed.
- Mailbox mode fails closed without `UAGENT_SEED`; the operator runbook keeps seed entry process-local and out of chat/docs/history.
- Config now enforces that identity secrets are not carried in YAML/direct config.
- Source claims cite official URLs, local cache/source files, or implementation/test evidence.

## Final agreement state

`research/HERMES_CODEX_DONE_STATUS.md` records `BLOCKED_OPERATOR_ONLY`.

Reason: local gates pass and docs are coherent, but live hosted Agentverse/mailbox proof and any testnet/real-value payment proof remain exact operator-owned actions. See `research/OPERATOR_ACTIONS_TO_FINISH.md`.

## Residual risks

- Dirty working tree needs human review before commit/PR/merge.
- Hosted Agentverse/mailbox proof requires operator account, seed, remote sender/linking, and sanitized transcript evidence.
- Testnet/sandbox and real-value payment proof require separate operator approval, rail choice, limits, credentials, and settlement verification.
