# Troubleshooting

## Hermes MCP stdio unavailable

`hermes mcp serve` must be reachable for the Hermes-backed stdio demo. Use:

```bash
python -m hermes_fetch_ai.cli probe-hermes
python -m hermes_fetch_ai.cli doctor --config examples/hermes-stdio.yaml --probe-backend
```

If the `hermes` console script is not on PATH but you have a Hermes source checkout, set `HERMES_FETCH_HERMES_PYTHON` to that checkout's venv Python and use `examples/hermes-stdio-env.yaml`.

## Address in use

Change `agent.port` in the selected YAML file.

## Tool not allowed for sender

Add the tool to `policy.public_tools` for a demo, or add the sender address to `policy.allowed_senders` with the exact tool names.

## Schema validation failed

Check the tool input schema in ListTools and send an object matching required fields and types.

## No UAGENT_SEED for mailbox

Set `UAGENT_SEED` in the environment. Do not write it in YAML.

## Windows executable, environment, or stderr issues

Use an absolute command path for stdio mode when needed. The bridge passes only a small environment allowlist to child processes and redirects stderr away from protocol stdout. Prefer putting local paths in environment variables rather than committing machine-specific YAML.
