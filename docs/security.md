# Security

Threat model:

- Remote senders may enumerate tools or call expensive or sensitive tools.
- Tool arguments may include local/private URLs, shell metacharacters, or oversize payloads.
- Tool outputs may contain secrets or very large content.
- Subprocess transports may leak data via environment or stderr.

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

Hermes surface boundary:

- The bridge only ever targets the Hermes tools MCP server
  (`agent.transports.hermes_tools_mcp_server`), preferably as an isolated stdio
  subprocess.
- The Hermes conversations MCP surface (`hermes mcp serve`: reading conversations,
  sending messages, answering permission approvals) is structurally out of scope and
  must never be bridged across an agent network.
- `skill_view` is not demo-public because it can reveal private skill content.
