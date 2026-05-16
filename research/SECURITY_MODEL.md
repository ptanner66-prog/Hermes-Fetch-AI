# Security Model

> Hardened note (2026-05-16): For final v1 decisions, see `research/HARDENED_ARCHITECTURE_DECISION.md`, `research/HARDENED_BUILD_PROMPT.md`, and `research/HARDENING_AUDIT.md`. Where this file disagrees with the hardened deliverables, the hardened deliverables are authoritative.

Date accessed: 2026-05-16

## Core rule

Agentverse/uAgents discovery is identity and routing, not trust. A sender address can tell the bridge who a message claims to be in the uAgents system; it does not authorize access to local Hermes tools.

## Assets

- `UAGENT_SEED`: private identity key. Leaking it allows impersonation.
- Agentverse/mailbox token: authorizes account/team linking and mailbox operation.
- `ASI1_API_KEY`: model-service credential for optional chat path.
- Hermes provider API keys in `~/.hermes/.env` or environment.
- Hermes local files, tools, browser/session state, credentials, memory, and logs.
- Bridge audit logs.
- Public endpoint URL and agent address.

## Threats

- Unknown remote agent invokes privileged Hermes tool.
- Prompt injection through remote messages causes Hermes to reveal secrets or take side effects.
- Tool-call argument injection causes shell/file/network misuse.
- Sender spoofing/replay at application level.
- Seed or token accidentally committed/logged.
- ASI chat path leaks prompt/tool output to hosted model service unexpectedly.
- Large payload/output causes denial of service or log exfiltration.
- Public endpoint scanned/abused.
- MCP server crash/hang blocks uAgent event loop.
- Adapter synchronous HTTP call blocks async runtime under load.

## Default controls

### Secrets

- `.env`, `.env.*`, keys, certs, logs, caches, virtualenvs, and `node_modules` are ignored.
- Examples use placeholders only.
- Bridge refuses to start without `UAGENT_SEED` unless explicit dev mode is set.
- Do not print seed/token/API key values, even masked, unless in a diagnostic that only says configured/not configured.
- Redact token-like strings in logs.

### Authorization

- Default deny all remote tool calls.
- Config must explicitly allow public tools.
- `ListTools` is also an authorization surface: unknown senders see only explicitly public-safe tool schemas or an empty list.
- Non-public tools require sender allowlist.
- Side-effecting tools require a stricter allowlist and future operator approval hook.
- Agent address or Agentverse listing alone never grants permission.

### Input validation

- Validate uAgent message model and MCP tool args.
- Enforce max payload bytes.
- Enforce JSON/schema validation before MCP call.
- Reject unknown tool names and denylisted tools.
- Normalize arguments; never construct shell commands from untrusted input.

### Execution limits

- Per-call timeout.
- Max concurrent tool calls.
- Max output chars/content blocks.
- Bounded retry/reconnect.
- Circuit breaker after repeated MCP failures.
- Do not publish chat protocol if `ASI1_API_KEY` is missing or `enable_chat` is false.

### Logging/audit

- JSONL audit log with redaction.
- Record decision metadata, not full secrets/prompts by default.
- Include trace id, sender, tool, allow/deny reason, duration, sizes, error type.
- Store logs outside repo.
- Never log raw `UAGENT_SEED`, Agentverse token, ASI key, or Hermes provider credentials.

### Network modes

- Local endpoint mode for CI.
- Mailbox mode for NAT-friendly demo.
- Public endpoint/proxy only after policy and rate limits are verified.
- Public endpoint should require HTTPS in production.

## Tool risk tiers

Tier 0: fake/demo tools such as echo/status. Public-safe for local demo.

Tier 1: read-only metadata tools with no secrets and no filesystem access. May be public if output is bounded.

Tier 2: read-only but potentially sensitive local context. Requires sender allowlist.

Tier 3: side-effecting actions: file writes, terminal, network posts, external API mutation, messages, browser automation, purchases, deploys. Deny in v1 unless a highly explicit operator-approved demo requires one.

Tier 4: credential/config/memory export or unrestricted terminal/filesystem. Out of scope for public v1.

## Prompt injection stance

Remote messages are untrusted user input. They must not be appended to privileged system prompts that can override Hermes policies. If the bridge uses ASI chat tool selection, ASI sees only tool schemas and user text needed for the demo, and the bridge still enforces policy after the model selects a tool.

## Credential appearances in flow

- `UAGENT_SEED`: read at bridge startup; derives address; never leaves process intentionally.
- Agentverse token/mailbox credential: used during mailbox/Inspector linking; never logged or committed.
- `ASI1_API_KEY`: used only by adapter chat path; not needed for direct protocol.
- Hermes credentials: remain in Hermes environment/config; bridge should not copy them.

## Required tests

- Missing seed fails safe.
- Unknown sender `ListTools` returns only public-safe tools or an empty list.
- Unknown sender denied for non-public tool before shim/MCP invocation.
- Denied calls produce audit records and no MCP invocation.
- Unknown tool denied.
- Denylist overrides allowlist.
- Payload above cap denied.
- Output above cap truncated.
- Token-like strings redacted in audit logs.
- ASI chat not published without key/config but direct protocol still works.
- MCP timeout returns structured error.
- Public endpoint config emits warning unless explicit production settings are present.

## Security claims safe for README

- The bridge is default-deny.
- Remote uAgent identity is treated as identity/routing, not authorization.
- Tool exposure is allowlist-based.
- Secrets are environment/config based and ignored by git.
- Logs are redacted by default.

## Security claims to avoid

- Do not say the bridge makes Hermes safe to expose all tools publicly.
- Do not imply Agentverse verifies business authorization.
- Do not claim the system is hardened for arbitrary internet traffic before public endpoint testing.
