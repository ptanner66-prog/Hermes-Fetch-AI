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
- URLs must use `http` or `https`; `file:`, `data:`, `javascript:`, `ftp://`, and hostless URLs are rejected. A string counts as a URL when it starts with `scheme:/` or a known non-hierarchical scheme such as `data:`; ordinary text such as `Note: hello` is not treated as a URL.
- URLs embedded anywhere in a string (`see http://10.0.0.1/admin`) are checked too, as are bare local or literal-IP hosts (`localhost:8080`, `169.254.169.254/latest`, `[::1]:80`).
- URLs targeting localhost, non-global, private, link-local, multicast, unspecified, reserved, CGNAT/shared, or private DNS results are rejected. DNS lookups run off the event loop.
- Shell control characters (including newlines) and shell metacharacters (`; & | $ < > \` and backticks) are rejected unless a tool is listed in `policy.trusted_shell_tools`. This is deliberately strict: it also rejects URLs with query strings and multi-line text. Only list a tool there if it never passes arguments to a shell.
- Tool responses returned to callers are normalized and size-capped. They are not a DLP redaction boundary; only expose tools whose outputs are safe for the intended sender.
- Audit/log records never store raw arguments, raw outputs, full sender addresses, seeds, tokens, or keys.
- Stdio uses `shell=False`, a filtered environment, and stderr separated from protocol stdout.
- With `publish_manifest: false`, the bridge makes no outbound calls of its own. uAgents looks up the Almanac contract on the Fetch ledger whenever an agent is created and reports every agent as active or inactive to Agentverse's Almanac API, even with registration disabled; the bridge's `PrivateAgent` skips both. Replying to a remote agent can still look up that agent's endpoint in the Almanac.
- Production agent seeds must come from `UAGENT_SEED` and be at least 32 characters; YAML seed and mailbox key values are rejected.
- Config files are scanned for credential-shaped values anywhere, including inside lists such as `hermes_mcp.args`: bearer tokens, `sk-`/`pk-` keys, JWTs, long hex keys, `token=...`-style assignments, and secret flags such as `--api-key`. Ordinary words such as "token" in a description are allowed.
- In mailbox mode, the uAgents Agent Inspector endpoints (`/connect`, `/disconnect`) are unauthenticated. Keep the port firewalled to localhost and disable the inspector after connecting; see `docs/agentverse-mailbox.md`.

## Hermes boundary

The bridge targets the Hermes tools MCP server only:

```text
agent.transports.hermes_tools_mcp_server
```

That module is Hermes-version-dependent. If it is not present in the active Hermes installation, use the fake/local demo tier or wait for Hermes tools-server support before advertising a Hermes-backed production deployment.

The Hermes conversations/messaging MCP surface (`hermes mcp serve`: conversation reads, message sends, approval handling) is structurally out of scope and must not be bridged across an agent network.

`skill_view` is not demo-public because it can reveal private skill content. The Hermes-backed demo exposes `skills_list` only.

The `fetchai-bridge` Hermes plugin adds no tools, hooks, or middleware, so it changes nothing the Hermes agent can do on its own. It runs the bridge only when a user runs `hermes fetchai-bridge`, without a shell, and strips Hermes' Python variables from the bridge's environment. When it hands the bridge Hermes' interpreter, the tools server still starts with the bridge's environment allowlist, so Hermes settings such as `HERMES_YOLO_MODE` never reach it. Disclosures are in [`native-hermes-plugin.md`](native-hermes-plugin.md).

## Residual dependency risk

The dependency audit gate currently ignores two transitive vulnerabilities until upstream Fetch/uAgents constraints allow a compatible fix:

- `PyNaCl==1.6.0` via the `uagents/cosmpy` dependency chain: `CVE-2025-69277`.
- `ecdsa` via `uagents-core` and `cosmpy`: `PYSEC-2026-1325`, a Minerva timing side channel in python-ecdsa signing and key generation (signature verification is not affected). The python-ecdsa project treats side channels as out of scope, so no fixed version exists. The bridge signs every response envelope with its agent key through this library. Remote timing over a network is far noisier than local timing, and the bridge's global and per-sender rate limits cap how many signatures a caller can trigger, but an attacker who can precisely time signing on the same host is the realistic threat. Run the bridge on a host you control, and remove this exception when uagents moves to a constant-time signing backend.

Do not remove the ignore without confirming `uagents`, `cosmpy`, signing, and wallet behavior remain compatible with the fixed dependency. Track this as an upstream dependency exception, not as an application-level acceptance of arbitrary vulnerable code.

## Reporting vulnerabilities

Please report suspected vulnerabilities privately. Do not open a public issue containing exploit details, seeds, tokens, mailbox keys, private endpoints, or connection strings.

Preferred disclosure path for this repository:

1. Open a minimal GitHub security advisory if available, or contact the repository owner privately.
2. Include affected version/commit, reproduction steps, expected impact, and any safe proof of concept.
3. Redact all secrets as `[REDACTED]`.

Maintainers should acknowledge within 72 hours and publish a patched release or mitigation note once verified.
