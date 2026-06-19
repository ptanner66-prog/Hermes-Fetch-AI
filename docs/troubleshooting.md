# Troubleshooting

## ModuleNotFoundError: mcp_serve

`hermes mcp serve` may not be available in the installed Hermes version and is not the tools surface this bridge wants. Use fake mode for CI, `examples/hermes-stdio.yaml` for the Hermes tools MCP server, and `probe-hermes` to report local status.

## Address in use

Change `agent.port` in the selected YAML file. The HTTP smoke test uses a dynamic port; production configs should use a fixed operator-owned port.

## Tool not allowed for sender

Add the tool to `policy.public_tools` for a demo, or add the sender address to `policy.allowed_senders` with exact tool names. Denylist entries always win.

## Missing replay metadata

`CallTool` requires replay/idempotency metadata by default. Add a reserved `_hermes_fetch_ai` object to args:

```json
{
  "_hermes_fetch_ai": {
    "request_id": "unique-client-request-id",
    "issued_at_ms": 1780000000000
  }
}
```

The bridge strips this key before schema validation and tool invocation. Generate a fresh request ID for each attempted call.

## Replay detected

The sender reused a request ID within `policy.replay_ttl_seconds`. Treat the response as final. Do not retry a potentially side-effectful tool call with the same request ID.

## Stale or future replay metadata

Check client clock skew and `issued_at_ms`. The default TTL is 300 seconds and the default future skew allowance is 60 seconds.

## Schema validation failed

Check the tool input schema in `ListTools` and send an object matching required fields and types. Hermes tools MCP handlers usually expect a top-level `kwargs` object.

## No UAGENT_SEED for hosted mode

Set `UAGENT_SEED` in the environment. Do not write it in YAML.

## Windows executable, environment, or stderr issues

Use an absolute command path for stdio mode when needed. The bridge passes only a small environment allowlist to child processes and redirects stderr away from protocol stdout.
