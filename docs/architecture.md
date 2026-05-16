# Architecture

Hermes Fetch AI has three layers:

1. Fetch/uAgents identity and messaging provide signed sender addresses and delivery.
2. The bridge filters list/call messages through policy, argument validation, redaction, audit, and output normalization.
3. Hermes or fake MCP tools execute locally behind the shim.

Message flow:

sender -> uAgent direct protocol -> policy and validation -> MCP shim -> local tool -> normalizer -> response

Trust boundaries:

- Sender address is not enough to authorize a tool call.
- Tool inventory is filtered and rate-limited because list responses can disclose capability information.
- MCP subprocesses run with `shell=False`, a filtered environment, and stderr separated from protocol output.
- Hosted registration is disabled in local configs.

Existing Fetch, Hermes, and MCP rails are sufficient for v1. The bridge only connects them with local policy and audit.

`MCPServerAdapter.protocols` is not used as the v1 security boundary because it exposes protocol behavior before this package's policy checks. Chat is out of v1 scope to keep the surface narrow.
