# Upstream PR Package Plan

## PR objective

Package the Hermes Fetch AI work as a thin, source-backed bridge between Hermes local runtime and Fetch/uAgents/Agentverse rails.

Do not present the PR as:

- a marketplace launch;
- wallet custody;
- real FET/mainnet payment settlement;
- a complete hosted Agentverse proof unless the operator runs and records that proof;
- a general public tunnel to all Hermes tools.

## Files in scope for this continuation pass

Allowed edits:

- `research/**`.
- `docs/**`.
- `README.md`.

Not edited in this pass:

- implementation files under `src/**`;
- tests;
- examples;
- package config;
- CI.

If verification finds implementation/test defects, record them in `research/PR_REVIEW_REPORT.md` with file:line evidence and minimal fix.

## Required artifacts in the PR package

Research artifacts:

- `research/AGENTIC_ECONOMY_MASTER_REPORT.md`.
- `research/FETCH_RAILS_DEEP_MAP.md`.
- `research/HERMES_AS_FETCH_AGENT_BLUEPRINT.md`.
- `research/AGENTIC_ECONOMY_PRODUCT_STRATEGY.md`.
- `research/PAYMENT_AND_INCENTIVE_RAILS_STRATEGY.md`.
- `research/SECURITY_TRUST_AND_GOVERNANCE_MODEL.md`.
- `research/UPSTREAM_PR_PACKAGE_PLAN.md`.
- `research/AGENTIC_ECONOMY_ADVERSARIAL_REVIEW.md`.
- `research/UPSTREAM_PR_DESCRIPTION.md`.
- `research/UPSTREAM_PR_REVIEW_CHECKLIST.md`.
- `research/PR_REVIEW_REPORT.md`.
- `research/PR_REVIEW_STATUS.md`.

Public docs:

- `docs/fetch-uagents-bridge.md`.
- `docs/agentverse-hosted-proof.md`.
- `docs/payment-rails.md`.
- `docs/agentic-economy-thesis.md`.
- `README.md` links.

Run metadata:

- `research/agentic-economy-research-company/source-ledger.md`.
- `research/agentic-economy-research-company/compliance-matrix.md`.
- `research/agentic-economy-research-company/run-state.txt`.

## PR story

Suggested title:

`Document Hermes Fetch AI bridge proof and agentic-economy rails strategy`

Suggested summary:

- Adds source-backed docs explaining the Hermes Fetch AI bridge: Hermes as local runtime, Fetch/uAgents/Agentverse/Almanac as rails.
- Adds public docs for the bridge, Agentverse hosted proof boundaries, payment rails, and the agentic-economy thesis.
- Adds research artifacts, source ledger, compliance matrix, adversarial review, and PR review/checklist files.
- Keeps v1 thin: local proof, mailbox/hosted runbook, dry-run payment proof, no wallet custody, no real-value movement.

## Evidence reviewers should inspect

1. Source ledger:
   - `research/agentic-economy-research-company/source-ledger.md`.

2. Public docs:
   - `docs/fetch-uagents-bridge.md`.
   - `docs/agentverse-hosted-proof.md`.
   - `docs/payment-rails.md`.
   - `docs/agentic-economy-thesis.md`.

3. Security model:
   - `research/SECURITY_TRUST_AND_GOVERNANCE_MODEL.md`.

4. Payment strategy:
   - `research/PAYMENT_AND_INCENTIVE_RAILS_STRATEGY.md`.

5. Verification output:
   - `research/PR_REVIEW_REPORT.md` and `research/PR_REVIEW_STATUS.md`.

## Verification set

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
- `.venv\Scripts\python.exe -m hermes_fetch_ai.cli demo mailbox --config examples\agentverse-mailbox-hermes.yaml --duration-seconds 5` with no `UAGENT_SEED`; expected fail-closed.

## Review criteria

Green if:

- Required artifacts/docs exist.
- Source claims cite official URLs or local files.
- Tests/lint/type/demo checks pass, with the no-seed mailbox command failing closed as expected.
- No secrets/private project content appear in public docs.
- Payment docs do not overclaim settlement.

Yellow if:

- Docs/artifacts complete, but a hosted proof or real settlement remains operator-only.
- A verification command is environment-dependent but the failure is explained and not a code defect.

Red if:

- Required local tests/lint/type checks fail due a repo defect.
- Docs contain secrets/private content.
- The bridge exposes unsafe public tools or claims real payment settlement without proof.

## Operator-only follow-up after PR package

- Decide whether to run Agentverse hosted/mailbox proof with real account/API key/seed/public endpoint.
- Decide whether to run testnet/sandbox payment proof.
- Decide whether any implementation/test fixes outside this pass should be patched.
- Merge/open upstream PR only after human review.
