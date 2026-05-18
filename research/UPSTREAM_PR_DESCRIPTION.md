# Upstream PR Description

## Title

Document Hermes Fetch AI bridge proof and agentic-economy rails strategy

## Summary

This PR package documents Hermes Fetch AI as a thin, policy-aware bridge between the Hermes local runtime and Fetch/uAgents/Agentverse/Almanac rails.

It adds:

- A source-backed master report and rails map.
- A Hermes-as-Fetch-agent blueprint.
- Product, payment, security, and governance strategy docs.
- Public docs for the bridge, hosted proof boundaries, payment rails, and the agentic-economy thesis.
- A source ledger, compliance matrix, adversarial review, PR checklist, PR review report, and takeover-readiness review.
- README links to the new public docs.

## Thesis

Hermes is the agent runtime. Fetch/uAgents/Agentverse/Almanac are the rails.

The bridge should expose only a small, policy-governed subset of Hermes capability through uAgents-compatible flows. Fetch rails provide identity/addressing, registration/discovery, mailbox/proxy/hosted surfaces, adapter interoperability, quotas, and payment negotiation primitives.

## Scope

In scope:

- Local proof documentation.
- Agentverse hosted/mailbox proof runbook and limitations.
- Dry-run payment proof using official uAgents-core payment models.
- Security/trust model emphasizing that identity is not authorization.
- Source-backed PR review materials.

Out of scope:

- Marketplace features.
- Wallet custody.
- Real FET/mainnet movement.
- Real Stripe/Skyfire settlement.
- Public exposure of broad Hermes toolsets.
- Private project/legal-tech content.

## Source basis

Primary source ledger:

- `research/agentic-economy-research-company/source-ledger.md`.

Key official sources cited:

- Agentverse external uAgents / ACP registration: https://docs.agentverse.ai/documentation/launch-agents/external-agents/u-agents.
- Agentverse mailbox submit API: https://docs.agentverse.ai/api-reference/agents/submit-mailbox-message.
- Agentverse mailbox/error and quota behavior: https://docs.agentverse.ai/documentation/advanced-usages/agent-logs-errors.
- Agent Payment Protocol: https://uagents.fetch.ai/docs/guides/agent-payment-protocol.
- uAgents repository and installed package metadata referenced by the source ledger.

Raw source caches and runner logs are intentionally excluded from the PR payload.

## Verification

Final verification output is recorded in:

- `research/PR_REVIEW_REPORT.md`.
- `research/PR_REVIEW_STATUS.md`.
- `research/AGENTVERSE_TAKEOVER_READINESS_REVIEW.md`.

Required commands:

- `git status --short --branch`.
- `git diff --stat`.
- `.venv\Scripts\python.exe -m pytest -q`.
- `ruff check .`.
- `python -m mypy src\hermes_fetch_ai --ignore-missing-imports`.
- `.venv\Scripts\python.exe -m hermes_fetch_ai.cli doctor --config examples\agentverse-mailbox-hermes.yaml --probe-backend`.
- `.venv\Scripts\python.exe -m hermes_fetch_ai.cli demo local`.
- `.venv\Scripts\python.exe -m hermes_fetch_ai.cli demo payment --config examples\payment-dry-run.yaml`.
- `.venv\Scripts\python.exe -m hermes_fetch_ai.cli doctor --config examples\agentverse-mailbox-hermes.yaml --contamination-scan`.
- `.venv\Scripts\python.exe -m hermes_fetch_ai.cli demo mailbox --config examples\agentverse-mailbox-hermes.yaml --duration-seconds 5` without `UAGENT_SEED` (expected fail-closed).

## Risk notes

- Agentverse/uAgent identity is identity, not trust.
- Hosted Agentverse proof requires operator credentials/account/seed/public endpoint and is not overclaimed.
- Payment proof is dry-run only unless a separate operator-approved testnet/sandbox or mainnet plan is executed.
- No real funds should move from this PR.
- No secrets are expected in docs/config output.

## Reviewer checklist

See `research/UPSTREAM_PR_REVIEW_CHECKLIST.md`.
