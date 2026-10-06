# Troubleshooting

## ModuleNotFoundError: mcp_serve

`hermes mcp serve` may not be available in the installed Hermes version and is not the tools surface this bridge wants. Use fake mode for CI, `examples/hermes-stdio.yaml` for the Hermes tools MCP server, and `probe-hermes` to report local status.

## hermes backend: FAIL

`serve` could not start the Hermes tools MCP server and exited with status 1. The message says why:

- `command not found`: `hermes_mcp.command` does not exist. Use the absolute path to the Python interpreter of the environment where `hermes-agent` is installed.
- `McpError: Connection closed`: the server process exited during startup, usually because `agent.transports.hermes_tools_mcp_server` is not importable in that environment, or Hermes was installed without its `mcp` extra (`pip install -e "<hermes-agent checkout>[mcp]"`).
- `timed out`: the server did not finish initializing within `hermes_mcp.timeout_seconds`.

The child's stderr is discarded on purpose (it is outside the bridge's redaction boundary). The message names the command to run by hand to see it, for example `/path/to/hermes-venv/bin/python -m agent.transports.hermes_tools_mcp_server`.

## hermes_mcp.command is required for stdio mode

The config uses `mode: stdio` without `command`, and the bridge was not started by the Hermes plugin. Either run it as `hermes fetchai-bridge serve --config ...` (the plugin supplies Hermes' interpreter), or set `hermes_mcp.command` to the Python interpreter of the Hermes environment.

## fetchai-bridge: 'hermes-fetch-ai' not found

The Hermes plugin could not find the bridge. Install it in its own environment with `uv tool install --python 3.12 "hermes-fetch-ai @ git+https://github.com/ptanner66-prog/Hermes-Fetch-AI"`, or set `plugins.entries.fetchai-bridge.settings.command` to the full path of `hermes-fetch-ai`.

## hermes: 'fetchai-bridge' is not a `hermes` command

Hermes did not load the plugin's command. Check that it is enabled (`hermes plugins list`; enable it with `hermes plugins enable fetchai-bridge`) and that `plugins.isolation` is not `host`, which skips plugin CLI commands. Under host isolation, run `hermes-fetch-ai` directly.

## backend unavailable

The Hermes backend stopped responding after startup. The audit log records `decision: error` with the `error_class`. Restart the bridge (systemd `Restart=on-failure` does not trigger while the process is still running).

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

## Shell metacharacters or control characters are not allowed

Arguments containing `; & | $ < > \`, backticks, or control characters such as newlines are rejected by default. That includes URLs with query strings (`?a=1&b=2`) and multi-line text. If a tool never hands its arguments to a shell, add its exact name to `policy.trusted_shell_tools`. URL checks still apply to trusted tools.

## Schema validation failed

Check the tool input schema in `ListTools` and send an object matching required fields and types. hermes-agent v0.16.x expected a top-level `kwargs` object; newer releases expect flat arguments, so always follow the served schema.

## No UAGENT_SEED for hosted mode

Set `UAGENT_SEED` in the environment. Do not write it in YAML.

## UAGENT_SEED must be at least 32 characters

The agent's signing key is derived from the seed, so short seeds are rejected. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"`.

## seed: WARN ... dev_random_seed is true

The config has `agent.dev_random_seed: true`, so `UAGENT_SEED` is ignored and the bridge gets a new address on every start. Set `agent.dev_random_seed: false` for a stable identity.

## secret-shaped YAML values are not allowed

The config contains something that looks like a credential: a bearer token, an `sk-`/`pk-` key, a JWT, a long hex key, a `token=...` assignment, or a flag such as `--api-key` in `hermes_mcp.args`. Pass secrets through the environment instead.

## Windows executable, environment, or stderr issues

Use an absolute command path for stdio mode when needed. The bridge passes only a small environment allowlist to child processes and redirects stderr away from protocol stdout.
