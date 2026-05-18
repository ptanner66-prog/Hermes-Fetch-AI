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

For the local A2A HTTP proof, change `a2a.port` in `examples/a2a-local.yaml`.

## Tool not allowed for sender

Add the tool to `policy.public_tools` for a demo, or add the sender address to `policy.allowed_senders` with the exact tool names.

## Schema validation failed

Check the tool input schema in ListTools and send an object matching required fields and types.

## No UAGENT_SEED for mailbox

Set `UAGENT_SEED` in the environment. Do not write it in YAML.

## Agentverse asks which stack to use

Choose **A2A Protocol**. Agent Chat Protocol is not the target path for this bridge. The local A2A proof is:

```bash
python -m hermes_fetch_ai.cli demo a2a --config examples/a2a-local.yaml
```

If Agentverse asks for a public URL or agent card, use the A2A proof/runbook in `docs/agentverse-hosted-proof.md` and keep credentials out of repo files.

## Mailbox starts locally but hosted messages do not arrive

Check the hosted proof boundaries in `docs/agentverse-hosted-proof.md`: account login, A2A Protocol selection, endpoint or agent-card requirements, and the bridge address printed by the startup command. The local proof cannot complete hosted registration without operator account access. Mailbox evidence is supporting transport evidence unless Agentverse requires it for the selected A2A path.

## Payment dry-run works but real settlement is unavailable

That is expected. `uagents_core.contrib.protocols.payment` supplies negotiation messages, not fund settlement. This repo only proves disabled-by-default dry-run rails. Testnet or production settlement requires explicit operator setup and must not be attempted by CI.

## Windows executable, environment, or stderr issues

Use an absolute command path for stdio mode when needed. The bridge passes only a small environment allowlist to child processes and redirects stderr away from protocol stdout. Prefer putting local paths in environment variables rather than committing machine-specific YAML.
