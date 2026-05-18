# Agentic Economy Adversarial Review

Reviewer posture: assume the bridge will be misunderstood, overexposed, or overclaimed unless the docs and run-state are precise.

## Finding 1: The thesis can drift into hype

Risk:

- "Agentic economy" language can sound like a broad marketplace or autonomous commerce launch.

Evidence:

- Official Agentverse docs mention discoverability/monetization options (`raw/external-sources/agentverse-external-uagents.md`), but the local repo only proves a bridge and dry-run payment.

Required correction:

- Use the narrow thesis everywhere: Hermes is the runtime; Fetch/uAgents/Agentverse/Almanac are rails.
- Keep v1 to local proof, hosted proof runbook, dry-run payment, and safety docs.

Status: addressed in research and public docs.

## Finding 2: Identity could be mistaken for trust

Risk:

- A signed uAgent message, Agentverse listing, or Almanac registration might be treated as permission to call Hermes tools.

Evidence:

- Official sources prove identity/addressing/delivery rails: `uagents-github-agent.py`, `agentverse-api-register-agent.md`, `agentverse-api-submit-mailbox.md`, `uagents-github-registration.py`.
- Local code must enforce policy separately: `src/hermes_fetch_ai/policy.py`, `direct_protocol.py`.

Required correction:

- Public docs must explicitly say identity is not authorization.
- Unknown senders must only get public tools if configured.

Status: addressed; verify with tests and docs self-audit.

## Finding 3: Hosted proof could be overclaimed

Risk:

- A local mailbox config or official Agentverse documentation could be presented as a completed hosted Agentverse proof.

Evidence:

- External uAgents docs require Agentverse API key, seed phrase, and reachable public endpoint (`raw/external-sources/agentverse-external-uagents.md`).
- Hosted Agents docs describe Agentverse-managed agents (`raw/external-sources/agentverse-hosted-agents.md`), but this pass did not run an operator account flow.

Required correction:

- Public hosted-proof doc must say what is proven locally and what remains operator-only.
- Final status should be yellow or operator-blocked if live hosted proof is a required release criterion.

Status: addressed in docs; final run-state depends on verification results and scope interpretation.

## Finding 4: Payment settlement could be overclaimed

Risk:

- Using official `RequestPayment`/`CommitPayment` models may be mistaken for moving real funds.

Evidence:

- Official payment source proves message models and interaction graph (`raw/external-sources/uagents-core-payment.py`).
- Payment guide lists rail identifiers (`stripe`, `skyfire`, `fet_direct`) (`raw/external-sources/fetch-agent-payment-protocol.md`).
- Local implementation is dry-run only (`src/hermes_fetch_ai/payments.py`, `tests/test_payment_policy.py`).

Required correction:

- Docs must distinguish dry-run, sandbox/testnet, and real-value/mainnet.
- Real-value movement requires explicit operator approval.

Status: addressed in payment strategy and public docs.

## Finding 5: Tool exposure is the largest real security risk

Risk:

- Hermes has powerful tools. Public exposure of broad toolsets would be unsafe.

Evidence:

- Upstream toolsets include terminal/process, file write/patch, browser, message sending, delegation, memory, etc. (`../hermes-agent-main/toolsets.py`).
- Hermes MCP server exposes message send/permission surfaces (`../hermes-agent-main/mcp_serve.py`).

Required correction:

- V1 public tools should stay minimal.
- Side-effecting tools remain private/operator-gated.
- Docs must not suggest a generic public MCP tunnel.

Status: addressed; verification should confirm allowlist behavior.

## Finding 6: Secret leakage risk is non-negotiable

Risk:

- Agentverse API keys, seeds, wallet keys, Stripe client secrets/session IDs, and local private paths could leak into public docs or audit output.

Evidence:

- External Agentverse flows require secrets/operator credentials (`raw/external-sources/agentverse-external-uagents.md`).
- Payment docs show example Stripe metadata fields (`raw/external-sources/fetch-agent-payment-protocol.md`), which must not be copied with real values.

Required correction:

- No `.env` inspection.
- Use placeholders only.
- Run contamination scan and textual self-audit.

Status: no secrets intentionally written; scan pending.

## Finding 7: Official source/guide role mismatch should not be hidden

Risk:

- Cached payment guide role wording may differ from official source code roles.

Evidence:

- `raw/external-sources/uagents-core-payment.py` role map differs from the cached guide snippet in `raw/external-sources/fetch-agent-payment-protocol.md`.

Required correction:

- Prefer source code for implementation claims.
- Mention discrepancy as caveat if discussing roles.

Status: recorded in payment strategy.

## Finding 8: Existing implementation changes are outside this pass authority

Risk:

- The continuation pass sees source/test/example changes from earlier work. If verification fails, it must not patch code in this pass.

Evidence:

- `git status --short --branch` showed modified/untracked implementation/test/example files before docs were written.

Required correction:

- Record failures with file:line evidence and minimal fix in `PR_REVIEW_REPORT.md`.
- Do not patch code/test/example files in this pass.

Status: adhered to so far.

## Adversarial conclusion

The package is acceptable only if it remains a bridge proof with explicit limits. The strongest version of the story is not "Hermes can sell tools autonomously today." It is:

Hermes can expose a carefully governed local runtime through Fetch rails, prove local/dry-run behavior now, and leave hosted and real-value steps as explicit operator-controlled proofs.
