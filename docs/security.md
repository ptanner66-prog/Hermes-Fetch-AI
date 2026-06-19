# Security

Hermes Fetch AI bridges a local Hermes tools surface onto a uAgent network, so the security posture is intentionally conservative: small surface, default deny, explicit replay protection, bounded resources, and redacted audit.

## Threat model

Remote senders may:

- enumerate tools to learn local capability information;
- replay signed `CallTool` messages;
- rotate sender identities to bypass per-sender rate limits;
- submit expensive or sensitive tool calls;
- pass unsupported URL schemes, local/private URLs, shell-control characters, oversized payloads, or schema-invalid arguments;
- trigger outputs containing secrets or very large content;
- exploit subprocess transport stderr/environment leakage.

## Controls

- Default deny for tool calls.
- Denylist wins over allowlists and public tools.
- Sender identity is routing evidence, not authorization by itself.
- `ListTools` is filtered, rate-limited globally/per sender, and size-capped.
- `CallTool` is rate-limited globally/per sender before expensive validation.
- `CallTool` requires bridge replay/idempotency metadata by default:
  - metadata is carried under reserved args key `_hermes_fetch_ai`;
  - `request_id` must be unique per sender within the replay TTL;
  - `issued_at_ms` must be fresh and not too far in the future;
  - duplicate, stale, malformed, or oversized calls are denied before tool invocation;
  - the replay cache is TTL-pruned and max-entry bounded;
  - schema-invalid requests do not poison a request ID for a corrected retry.
- Arguments are schema-validated and size-capped before invocation.
- URL-like strings must use `http` or `https`; `file:`, `data:`, `ftp:`, and hostless URLs are rejected.
- URL-like strings targeting localhost, non-global, private, link-local, multicast, unspecified, reserved, CGNAT/shared, or private DNS results are rejected.
- Shell control characters and shell metacharacters are rejected unless a tool is explicitly trusted for shell-like input.
- Tool responses returned to callers are normalized and size-capped. They are not a DLP redaction boundary; only expose tools whose outputs are safe for the intended sender.
- Audit/log records never store raw arguments, raw outputs, full sender addresses, seeds, tokens, or keys.
- Stdio uses `shell=False`, a filtered environment, and stderr separated from protocol stdout.
- Production agent seeds must come from `UAGENT_SEED`; YAML seed and mailbox key values are rejected.

## Hermes boundary

The bridge targets the Hermes tools MCP server only:

```text
agent.transports.hermes_tools_mcp_server
```

That module is Hermes-version-dependent. If it is not present in the active Hermes installation, use the fake/local demo tier or wait for Hermes tools-server support before advertising a Hermes-backed production deployment.

The Hermes conversations/messaging MCP surface (`hermes mcp serve`: conversation reads, message sends, approval handling) is structurally out of scope and must not be bridged across an agent network.

`skill_view` is not demo-public because it can reveal private skill content. The Hermes-backed demo exposes `skills_list` only.

## Residual dependency risk

The dependency audit gate currently ignores one transitive vulnerability until upstream Fetch/uAgents constraints allow a compatible fix:

- `PyNaCl==1.6.0` via the `uagents/cosmpy` dependency chain: `CVE-2025-69277`.

Do not remove the ignore without confirming `uagents`, `cosmpy`, signing, and wallet behavior remain compatible with the fixed dependency. Track this as an upstream dependency exception, not as an application-level acceptance of arbitrary vulnerable code.

## Reporting vulnerabilities

Please report suspected vulnerabilities privately. Do not open a public issue containing exploit details, seeds, tokens, mailbox keys, private endpoints, or connection strings.

Preferred disclosure path for this repository:

1. Open a minimal GitHub security advisory if available, or contact the repository owner privately.
2. Include affected version/commit, reproduction steps, expected impact, and any safe proof of concept.
3. Redact all secrets as `[REDACTED]`.

Maintainers should acknowledge within 72 hours and publish a patched release or mitigation note once verified.
