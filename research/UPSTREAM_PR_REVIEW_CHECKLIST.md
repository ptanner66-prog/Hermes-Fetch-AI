# Upstream PR Review Checklist

## Scope and authority

- [ ] PR edits are limited to intended files or separately authorized implementation/test changes.
- [ ] No `.env` content is inspected or committed.
- [ ] No API keys, seed phrases, wallet private keys, Stripe client secrets/session IDs, or connection strings appear in docs or artifacts.
- [ ] README links are concise and point to public docs.

## Thesis and positioning

- [ ] The thesis is stated as: Hermes is the runtime; Fetch/uAgents/Agentverse/Almanac are the rails.
- [ ] Docs are concrete and source-backed, not hype.
- [ ] V1 is thin: no marketplace sprawl, no wallet custody, no real-value movement.
- [ ] No private/legal-tech project examples are included in public docs.

## Fetch rails evidence

- [ ] Agentverse external uAgent/ACP registration claims cite `agentverse-external-uagents.md` or the official URL.
- [ ] Agentverse adapter claims cite `agentverse-adapters-overview.md` or the official URL.
- [ ] Hosted Agent claims cite `agentverse-hosted-agents.md` or the official URL and do not overclaim a completed hosted proof.
- [ ] Mailbox/proxy claims cite Agentverse API cache files.
- [ ] Almanac claims cite uAgents registration/resolver source cache files.
- [ ] uAgents/adapter package version claims cite cached pyproject files.

## Security and trust

- [ ] Agentverse/uAgent identity is described as identity/addressing evidence, not authorization.
- [ ] Default-deny and allowlist posture is documented.
- [ ] Public tools are minimal and low-risk.
- [ ] Argument validation, rate limiting, output caps, audit, and redaction are described.
- [ ] Operator-only authority boundaries are clear.

## Payment

- [ ] Payment protocol claims cite `uagents-core-payment.py` and/or `fetch-agent-payment-protocol.md`.
- [ ] Dry-run payment is clearly distinguished from settlement.
- [ ] Testnet/sandbox and real-value/mainnet are separate proof levels.
- [ ] No real-FET movement is claimed or performed without explicit operator approval.
- [ ] No wallet custody strategy is invented.

## Public docs

- [ ] `docs/fetch-uagents-bridge.md` is safe for public readers.
- [ ] `docs/agentverse-hosted-proof.md` states hosted proof prerequisites and limits.
- [ ] `docs/payment-rails.md` distinguishes disabled/dry-run/testnet/mainnet.
- [ ] `docs/agentic-economy-thesis.md` is source-backed and non-hype.
- [ ] Public docs contain no private paths except relative repo runbook paths where necessary.

## Verification

- [ ] `git status --short --branch` captured.
- [ ] `git diff --stat` captured.
- [ ] `.venv\Scripts\python.exe -m pytest -q` captured.
- [ ] `ruff check .` captured.
- [ ] `python -m mypy src\hermes_fetch_ai --ignore-missing-imports` captured.
- [ ] Backend probe command captured.
- [ ] Local demo command captured.
- [ ] Payment dry-run demo captured.
- [ ] Contamination scan captured.
- [ ] Mailbox demo without `UAGENT_SEED` captured and fails closed.

## Final status

- [ ] `research/PR_REVIEW_REPORT.md` records exact verification outcomes.
- [ ] `research/PR_REVIEW_STATUS.md` records verdict and residual risks.
- [ ] `research/agentic-economy-research-company/run-state.txt` is final and honest.
