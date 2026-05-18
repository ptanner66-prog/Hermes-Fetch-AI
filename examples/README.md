# Examples

- local-direct.yaml runs the offline fake MCP bridge and exposes only echo publicly.
- a2a-local.yaml runs the local A2A JSON-RPC proof path and publishes a local agent card with a policy-gated tool bridge.
- hermes-stdio.yaml is the portable Hermes MCP stdio demo config and assumes `hermes` is on PATH.
- hermes-stdio-env.yaml is for local source checkouts; set HERMES_FETCH_HERMES_PYTHON to the Hermes repo venv Python.
- hermes-local.yaml is kept as a compatibility alias for the Hermes MCP stdio demo.
- agentverse-mailbox.yaml is a supporting mailbox/Inspector transport smoke only. It uses fake MCP, Inspector enabled, and an empty public tool policy.
- agentverse-mailbox-hermes.yaml is a supporting real-Hermes mailbox smoke config. It uses Hermes MCP stdio, Inspector/manifest publication off by default, and an empty public tool policy.
- payment-dry-run.yaml is a CLI dry-run payment model proof only; it does not perform hosted payment negotiation or settlement.

Run:

python -m hermes_fetch_ai.cli demo local
python -m hermes_fetch_ai.cli demo a2a --config examples/a2a-local.yaml
python -m hermes_fetch_ai.cli demo hermes --config examples/hermes-stdio.yaml
