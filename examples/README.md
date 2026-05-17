# Examples

- local-direct.yaml runs the offline fake MCP bridge and exposes only echo publicly.
- hermes-stdio.yaml is the portable Hermes MCP stdio demo config and assumes `hermes` is on PATH.
- hermes-stdio-env.yaml is for local source checkouts; set HERMES_FETCH_HERMES_PYTHON to the Hermes repo venv Python.
- hermes-local.yaml is kept as a compatibility alias for the Hermes MCP stdio demo.
- agentverse-mailbox.yaml is for manual hosted mailbox setup and requires UAGENT_SEED.

Run:

python -m hermes_fetch_ai.cli demo local
python -m hermes_fetch_ai.cli demo hermes --config examples/hermes-stdio.yaml
