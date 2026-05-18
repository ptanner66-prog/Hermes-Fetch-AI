# Security, Trust, and Governance Model

## Core rule

Agentverse/uAgent identity is identity, not trust.

A signed envelope, uAgent address, Agentverse listing, mailbox, proxy, or Almanac registration may help route and attribute a message. None of those facts should authorize a Hermes tool call by itself.

Authorization remains local and explicit:

- default-deny tool policy;
- public tool allowlist;
- allowed sender policy;
- schema/argument validation;
- rate limits and output caps;
- payment gating when enabled;
- audit/redaction;
- operator approvals for sensitive actions.

## Source basis

Official rail evidence:

- uAgents identity/agent constructor: `raw/external-sources/uagents-github-agent.py`.
- Agentverse registration and external uAgents: `raw/external-sources/agentverse-api-register-agent.md`, `agentverse-external-uagents.md`.
- Mailbox/proxy signed envelope APIs: `raw/external-sources/agentverse-api-submit-mailbox.md`, `agentverse-api-submit-proxy.md`.
- Almanac registration/resolution: `raw/external-sources/uagents-github-registration.py`, `uagents-github-resolver.py`.

Local control evidence:

- Config and seed/payment gating: `src/hermes_fetch_ai/config.py`.
- Policy and protocol enforcement: `src/hermes_fetch_ai/policy.py`, `direct_protocol.py`.
- Argument validation: `src/hermes_fetch_ai/arg_validator.py`.
- Audit/redaction: `src/hermes_fetch_ai/audit.py`, `_redaction.py`.
- Mailbox startup/fail-closed tests: `tests/test_mailbox_startup.py`.
- Policy tests: `tests/test_direct_protocol_policy.py`.
- Contamination tests: `tests/test_contamination.py`.

Upstream Hermes reference:

- MCP server: `../hermes-agent-main/mcp_serve.py`.
- Toolsets: `../hermes-agent-main/toolsets.py`.
- Plugin hooks: `../hermes-agent-main/hermes_cli/plugins.py`.
- ACP permission denial on timeout/failure: `../hermes-agent-main/acp_adapter/permissions.py`.

## Threat model

### Threat: public caller invokes dangerous Hermes tools

Risk:

- Hermes has tools that can read/write files, run terminal commands, send messages, access browsers, use memory, delegate tasks, and more (`../hermes-agent-main/toolsets.py`). A public uAgent bridge to all tools would be unsafe.

Controls:

- `policy.default_allow: false`.
- `policy.public_tools` starts with low-risk tools only.
- Sender-specific allowlists for anything more sensitive.
- Side-effecting tools stay private/operator-gated by default.

### Threat: identity confusion

Risk:

- A valid-looking uAgent identity might be treated as trusted.

Controls:

- Treat sender address as an input to policy, not as authorization.
- Unknown senders only see public tools if configured.
- Full sender addresses are redacted in audit/public outputs.

### Threat: SSRF or local network probing through tool args

Risk:

- Public tool args could contain URLs targeting localhost/private networks/cloud metadata.

Controls:

- `src/hermes_fetch_ai/arg_validator.py` checks URLs and local/private targets before tool execution.
- Tests cover validation-deny-before-shim behavior in `tests/test_direct_protocol_policy.py`.

### Threat: shell injection or command smuggling

Risk:

- Arguments to downstream tools could include shell metacharacters.

Controls:

- Argument validator checks shell-like hazards.
- Public v1 should avoid terminal/shell tools entirely.

### Threat: oversize payloads or output exfiltration

Risk:

- Attackers can use large arguments or large outputs to exhaust resources or leak data.

Controls:

- Max argument bytes.
- Max output bytes.
- Max list-tools response bytes.
- Rate limits per sender.
- Deterministic truncation.

### Threat: secret leakage

Risk:

- Seeds, API keys, tokens, wallet keys, Stripe secrets, and private paths leak into docs/audit/output.

Controls:

- Do not inspect `.env`.
- Require `UAGENT_SEED` from environment for mailbox mode; do not store it in repo docs/config.
- Reject secret-shaped YAML config.
- Audit/redaction avoids raw args/outputs and secret-shaped values.
- Run contamination scan.

### Threat: payment overclaim or unauthorized fund movement

Risk:

- Dry-run payment gets mistaken for settlement; real-value rail is triggered without approval.

Controls:

- Payment defaults disabled.
- Dry-run uses synthetic IDs and no real funds.
- Real-shaped IDs are rejected in dry-run.
- `real_operator_approved` remains an operator stop.
- Public docs distinguish dry-run, sandbox/testnet, and mainnet.

### Threat: hosted proof overclaim

Risk:

- Docs imply Agentverse hosted proof is complete without live operator-run evidence.

Controls:

- Public docs state hosted proof requires Agentverse account/API key/seed/public endpoint and is operator-run.
- Run-state must be yellow or operator-blocked if hosted proof is required but not supplied.

## Governance boundaries

Operator-only boundaries:

- Setting or using `UAGENT_SEED`.
- Using Agentverse API keys.
- Publishing a public endpoint.
- Registering on mainnet or spending registration fees.
- Any wallet custody decision.
- Any real-value or payment processor settlement.
- Exposing new Hermes tools publicly.
- Merging upstream PRs or changing production deployments.

Assistant/pass authority boundaries:

- This pass may edit `research/**`, `docs/**`, and `README.md`.
- This pass may inspect implementation/tests/examples but must not patch them.
- If code/test issues are found, record file:line evidence and minimal fix in review artifacts.

## Minimum safe defaults

Recommended default config posture:

- `agent.mode: local` for docs/local proof.
- `agent.dev_random_seed: true` only for local non-production proof.
- `agent.mode: mailbox` requires `UAGENT_SEED` from env.
- `policy.default_allow: false`.
- `policy.public_tools: ["echo"]` for public demos.
- `payment.mode: disabled` unless running the dry-run payment demo.
- `audit` enabled.

## Release gate

A release/PR is acceptable only if:

1. Verification commands are recorded.
2. Mailbox without `UAGENT_SEED` fails closed.
3. Contamination scan passes.
4. Public docs contain no secrets/private project references.
5. Payment docs do not overclaim settlement.
6. Hosted proof docs do not overclaim Agentverse success.
7. Review status records any residual risk honestly.
