# Troubleshooting

## ModuleNotFoundError: mcp_serve

`hermes mcp serve` may not be available in the installed Hermes version. Use fake mode for CI and `probe-hermes` to report local status.

## Address in use

Change `agent.port` in the selected YAML file.

## Tool not allowed for sender

Add the tool to `policy.public_tools` for a demo, or add the sender address to `policy.allowed_senders` with the exact tool names.

## Schema validation failed

Check the tool input schema in ListTools and send an object matching required fields and types.

## No UAGENT_SEED for mailbox

Set `UAGENT_SEED` in the environment. Do not write it in YAML.

## Windows executable, environment, or stderr issues

Use an absolute command path for stdio mode when needed. The bridge passes only a small environment allowlist to child processes and redirects stderr away from protocol stdout.
