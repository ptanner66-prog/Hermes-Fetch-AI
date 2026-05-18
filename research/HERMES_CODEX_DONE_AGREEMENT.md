# Hermes/Codex Done Agreement

Updated: 2026-05-18T03:37:09Z

Final agreement status: BLOCKED_OPERATOR_ONLY

## Agreement

Hermes/Codex agree that the prior BLOCKED_OPERATOR_ONLY state needed another adversarial repo-local pass before it could be accepted. That pass found agent-solvable local issues and fixed them:

- config/seed fail-closed bypasses around YAML/direct `agent.seed`, empty runtime seed fallback, and env expansion;
- payment safety gaps around testnet/operator-stop handling and full transaction-like id echoing on dry-run cancellation;
- contamination coverage gaps between the public-tree test and the CLI scan.

After the fixes, local/offline verification is green. The repo is still not DONE_AGREED because live hosted Agentverse/mailbox proof and any payment proof beyond dry-run require operator-owned account access, process-local secrets, remote identity/linking, and/or explicit payment authorization. Human review/PR/merge authority also remains outside this agent pass.

## Scope reviewed

Required status/review/run-state files were read and updated where findings changed:

- research/HERMES_CODEX_DONE_STATUS.md
- research/HERMES_CODEX_DONE_AGREEMENT.md
- research/OPERATOR_ACTIONS_TO_FINISH.md
- research/PR_REVIEW_STATUS.md
- research/PR_REVIEW_REPORT.md
- research/agentic-economy-research-company/run-state.txt

Implementation/tests/examples/docs were inspected for:

- config/env expansion and fail-closed secret handling;
- Windows-sensitive Hermes stdio command path behavior;
- mailbox startup and no-seed failure behavior;
- payment dry-run and disabled-by-default rails;
- contamination scan coverage;
- docs contradictions or overclaims;
- README and PR package readiness.

No `.env` file was inspected.

## Verification command outcomes

Exact command outputs for the final overnight pass are preserved in:

- research/HERMES_OVERNIGHT_UNTIL_DONE_REPORT.md

Summary:

| Command | Exit | Outcome |
|---|---:|---|
| `git status --short --branch` | 0 | Branch `codex/full-hookup-proof`; dirty tree with tracked and untracked implementation/docs/research/examples/tests artifacts. |
| `git diff --stat` | 0 | Tracked diff present: 16 files changed, 879 insertions, 318 deletions; LF->CRLF warnings only. Untracked files not represented. |
| `.venv/Scripts/python.exe -m pytest -q` | 0 | `92 passed in 18.01s`. |
| `ruff check .` | 0 | `All checks passed!`. |
| `python -m mypy src/hermes_fetch_ai --ignore-missing-imports` | 0 | `Success: no issues found in 20 source files`. |
| mailbox Hermes backend probe | 0 | `backend: ok: 10 tools`; `doctor: ok`. |
| local demo | 0 | Bridge demo printed an address, visible tool count `1`, `echo result: hello`, audit event count `4`. |
| payment dry-run demo | 0 | Request/commit/complete dry-run succeeded; accepted `0.01 FET via fet_direct`; no real funds moved. |
| contamination scan | 0 | `contamination: ok`; `doctor: ok`. |
| mailbox demo with no `UAGENT_SEED` | 1 | Expected fail-closed negative proof: `UAGENT_SEED is required when agent.dev_random_seed=false`. |

## Documentation reconciliation

The public docs and README now remain consistent with implementation:

- Hermes is the local runtime; Fetch/uAgents/Agentverse/Almanac are rails.
- Local proof is not hosted proof.
- Mailbox mode fails closed without process-local `UAGENT_SEED`.
- Seeds/mailbox keys do not belong in YAML, docs, commits, chat, or screenshots; config now rejects them.
- Payment is disabled by default; implemented payment proof is dry-run only.
- `testnet` and `real_operator_approved` payment modes are operator stops in this repo-local proof.
- Dry-run transaction ids are `dryrun-*`; transaction-like ids are not echoed in full on dry-run cancellation.
- Public release-tree contamination scan is clean.

## Residual blockers

Operator-owned only:

1. Live hosted Agentverse/mailbox proof with operator account/login, process-local `UAGENT_SEED`, mailbox/endpoint/linking, remote sender identity, and sanitized transcript capture.
2. Optional testnet/sandbox payment proof, requiring a named rail, exact max amount/currency, recipient, process-local credentials/wallet setup, and explicit current-context approval.
3. Any real-value/mainnet payment proof, requiring separate explicit current-context approval plus rail/custody/fee/security/legal/commercial/incident planning.
4. Human review/commit/PR/merge decision for the dirty working tree.

Exact operator steps are listed in `research/OPERATOR_ACTIONS_TO_FINISH.md`.
