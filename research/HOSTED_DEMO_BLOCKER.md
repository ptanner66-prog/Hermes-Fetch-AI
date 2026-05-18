# Hosted Demo Blocker

Status: blocked only by operator-owned Agentverse/browser identity setup and process-local seed entry.

Local proof is green; hosted proof is pending. Do not claim hosted proof complete until `demo mailbox` runs with the real operator seed in-process and policy-denied public tool behavior is observed.

Use [NORMAL_HERMES_SECRET_TEST_RUNBOOK.md](NORMAL_HERMES_SECRET_TEST_RUNBOOK.md) for the current safe procedure.

Current precise blocker:

- Agentverse login and mailbox/agent identity confirmation must happen in the operator browser.
- `UAGENT_SEED` must be entered into a local PowerShell process, never chat, docs, commits, or shell history.
- Any Agentverse quota/subscription/funding UI prompt must be reviewed by the operator before continuing.
- Real FET movement is explicitly out of scope until the approval sentence in [FET_TEST_FUNDS_PLAN.md](FET_TEST_FUNDS_PLAN.md) is provided.

Expected hosted proof:

- The bridge starts with `examples\agentverse-mailbox-hermes.yaml`.
- The bridge uses normal Hermes MCP through `HERMES_FETCH_HERMES_PYTHON`.
- Startup output is redacted.
- Public tools remain denied unless allowlisted per sender.
- A missing seed fails closed.

Stop conditions:

- Stop if Agentverse asks for funding, paid quota, wallet authorization, public registration fees, or any real-value action.
- Stop if logs print any secret-like material.
- Stop if public tool exposure exceeds the config policy.
