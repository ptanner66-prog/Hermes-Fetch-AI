# Hermes as a Fetch Agent Blueprint

Purpose: turn the source-backed thesis into a concrete bridge blueprint without expanding v1 beyond safe proof scope.

## Design objective

Expose a small, policy-controlled Hermes runtime surface as a uAgent-reachable agent while keeping all dangerous authority local and operator-gated.

The bridge should answer:

- Can another agent discover or address a Hermes-backed agent through Fetch rails?
- Can that agent request a tightly allowlisted Hermes tool call?
- Can Hermes enforce local policy before any tool runs?
- Can payment negotiation be demonstrated without moving funds?
- Can hosted/Agentverse proof be run by an operator without embedding secrets in the repo?

It should not answer:

- Can Hermes custody wallets?
- Can arbitrary public users call arbitrary Hermes tools?
- Can we settle real FET/card/USDC payments automatically?
- Can we launch a general marketplace?

## Current repo shape

Local files inspected:

- Config: `src/hermes_fetch_ai/config.py`.
- Policy: `src/hermes_fetch_ai/policy.py`.
- Direct protocol: `src/hermes_fetch_ai/direct_protocol.py`.
- Arg validation: `src/hermes_fetch_ai/arg_validator.py`.
- MCP shim: `src/hermes_fetch_ai/mcp_shim.py`.
- uAgent app: `src/hermes_fetch_ai/uagent_app.py`.
- Payment dry-run: `src/hermes_fetch_ai/payments.py`, `payment_policy.py`, `payment_protocol.py`.
- CLI: `src/hermes_fetch_ai/cli.py`.
- Examples: `examples/local-direct.yaml`, `examples/agentverse-mailbox-hermes.yaml`, `examples/payment-dry-run.yaml`.
- Tests: `tests/test_direct_protocol_policy.py`, `tests/test_mailbox_startup.py`, `tests/test_payment_demo.py`, `tests/test_payment_policy.py`, `tests/test_config.py`, `tests/test_contamination.py`.

## Runtime architecture

1. Hermes MCP runtime
   - Upstream Hermes has a FastMCP stdio server (`../hermes-agent-main/mcp_serve.py`).
   - The bridge treats Hermes MCP as a local backend, not as a public network service.

2. Hermes Fetch shim
   - `src/hermes_fetch_ai/mcp_shim.py` lists/calls local fake or Hermes stdio tools.
   - It normalizes tool results and protects downstream protocol code from backend differences.

3. Policy layer
   - `src/hermes_fetch_ai/policy.py` and `direct_protocol.py` decide visible tools and allowed calls.
   - Sender identity is only an input to policy, not an authorization result by itself.

4. Validation layer
   - `src/hermes_fetch_ai/arg_validator.py` validates JSON schema, size limits, URL targets, and shell-like hazards before a backend call.

5. Audit layer
   - `src/hermes_fetch_ai/audit.py` and `_redaction.py` record safe metadata without raw secrets, raw args, raw outputs, or full sender addresses.

6. uAgent transport
   - `src/hermes_fetch_ai/uagent_app.py` wraps the bridge as a uAgent protocol.
   - Official uAgents source supports mailbox/proxy/endpoints/registration policy/network parameters (`raw/external-sources/uagents-github-agent.py`).

## Protocol boundary

V1 should expose two minimal actions over the direct protocol:

1. List public/visible tools.
2. Call an allowlisted tool with schema-valid args.

Everything else remains local or future work:

- Permission prompts stay local/operator-mediated.
- Message sending tools are not public by default.
- Filesystem/terminal/network tools require explicit allowlist and review.
- Chat Protocol/Agentverse adapter support is not the security boundary.

## Proof plan

### Level 1: Local proof

Goal: prove runtime/policy path without Agentverse.

Command:

`python -m hermes_fetch_ai.cli demo local`

Expected semantics:

- Builds a local bridge address.
- Lists a small visible tool set.
- Calls `echo` successfully.
- Writes/audits events without secrets.

Source references:

- `examples/local-direct.yaml`.
- `src/hermes_fetch_ai/cli.py`.
- `tests/test_direct_protocol_policy.py`.

### Level 2: Hermes stdio backend proof

Goal: prove the bridge can probe a real Hermes MCP backend.

Command pattern:

`python -m hermes_fetch_ai.cli doctor --config examples/agentverse-mailbox-hermes.yaml --probe-backend`

Caveat:

- This depends on local Hermes backend availability/config.
- It does not prove Agentverse hosted reachability.

Source references:

- `src/hermes_fetch_ai/mcp_shim.py`.
- `src/hermes_fetch_ai/cli.py`.
- Upstream `../hermes-agent-main/mcp_serve.py`.

### Level 3: Agentverse mailbox proof

Goal: prove a uAgent bridge can be started in mailbox mode with operator-provided identity.

Command pattern:

`python -m hermes_fetch_ai.cli demo mailbox --config examples/agentverse-mailbox-hermes.yaml --duration-seconds 5`

Requirements:

- Operator-supplied `UAGENT_SEED`.
- Agentverse account/API key if registering/exposing through Agentverse flows.
- Public endpoint or mailbox/proxy arrangement depending on chosen mode.

Negative proof:

- The same command without `UAGENT_SEED` must fail closed.

Source references:

- External uAgents docs: `raw/external-sources/agentverse-external-uagents.md`.
- Mailbox APIs: `raw/external-sources/agentverse-api-list-mailbox.md`, `agentverse-api-submit-mailbox.md`.
- Local tests: `tests/test_mailbox_startup.py`.

### Level 4: Payment dry-run proof

Goal: prove protocol-level payment gating without funds.

Command:

`python -m hermes_fetch_ai.cli demo payment --config examples/payment-dry-run.yaml`

Expected semantics:

- Creates a `RequestPayment` using official uAgents-core models.
- Accepts only dry-run shaped transaction IDs.
- Completes/cancels within the synthetic flow.
- Prints that no real funds moved.

Source references:

- Official source: `raw/external-sources/uagents-core-payment.py`.
- Official docs: `raw/external-sources/fetch-agent-payment-protocol.md`.
- Local implementation/tests: `src/hermes_fetch_ai/payments.py`, `tests/test_payment_policy.py`, `tests/test_payment_demo.py`.

### Level 5: Testnet/sandbox proof

Goal: move from dry-run to non-production rail verification.

Operator-only prerequisites:

- Sandbox/testnet account or wallet.
- Explicit written approval for the chosen rail.
- Captured transaction/session identifiers with secrets redacted.
- Rollback/cancel path documented.

Status: strategy only in this pass.

### Level 6: Real-value/mainnet proof

Goal: production settlement.

Status: out of automatic scope.

Required before any attempt:

- Explicit operator approval in the current context.
- Wallet custody decision owned by the operator.
- Legal/commercial review where applicable.
- Separate production change plan and rollback/incident plan.

## Configuration defaults

Recommended v1 defaults:

- `agent.mode: local` for local proof.
- `agent.mode: mailbox` only with `UAGENT_SEED` from environment.
- `policy.default_allow: false`.
- `policy.public_tools` limited to `echo` or similarly low-risk tools.
- `payment.mode: disabled` by default.
- `payment.mode: dry_run` only for payment demo/proof.
- `payment.mode: real_operator_approved` should stop config loading until an explicit operator flow exists.

## Public documentation boundaries

Public docs may say:

- Hermes can be bridged to Fetch/uAgents as a thin, policy-aware agent runtime.
- Local proof and dry-run payment proof exist.
- Agentverse hosted/mailbox proof requires operator credentials and endpoint/account setup.

Public docs must not say:

- Real FET settlement is implemented.
- Hosted Agentverse proof has completed unless verification artifacts exist.
- uAgent/Agentverse identity implies trust.
- The project is a marketplace or wallet.

## Minimal PR shape

1. Research artifacts and public docs.
2. README links to docs.
3. Verification results.
4. Review report and status.
5. No implementation/test edits from this continuation pass unless separately authorized.
