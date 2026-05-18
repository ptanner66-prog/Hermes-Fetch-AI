# Security

Threat model:

- Remote senders may enumerate tools or call expensive or sensitive tools.
- Tool arguments may include local/private URLs, shell metacharacters, or oversize payloads.
- Tool outputs may contain secrets or very large content.
- Subprocess transports may leak data via environment or stderr.
- Payment messages may be replayed, spoofed at the business-logic layer, or mistaken for authorization.

Controls:

- Default deny for tool calls.
- Denylist wins over allowlists and public tools.
- Sender identity is routing evidence, not authorization by itself.
- ListTools is filtered, rate-limited, and size-capped.
- Arguments are schema-validated and size-capped before invocation.
- URL-like strings targeting localhost, private, link-local, unspecified, or private DNS results are rejected.
- Shell metacharacters are rejected unless a tool is explicitly trusted for shell-like input.
- Outputs are normalized and truncated with a marker containing original byte count.
- Audit and logs redact tokens, keys, seeds, and long secret-shaped values. Audit records never store raw arguments or raw outputs.
- Stdio uses `shell=False`, a filtered environment, and separated stderr.

Payment controls:

- Payment mode defaults to `disabled`.
- The implemented proof mode is `dry_run`; it uses official uAgents payment message models and fake `dryrun-*` transaction ids only.
- `testnet` and real operator-approved settlement are operator-owned follow-up steps, not automatic behavior.
- Payment commitment never grants tool authorization. The bridge first applies sender/tool policy and argument validation; paid status cannot override a denied tool.
- No wallet secret, seed, recovery material, or production settlement credential belongs in YAML or this repository.
- Payment audit records include references, status, method, currency, amount, mode, and short transaction ids; they do not include raw tool arguments, raw outputs, or secrets.
