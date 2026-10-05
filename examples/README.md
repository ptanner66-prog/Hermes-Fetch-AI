# Examples

- local-direct.yaml runs the offline fake MCP bridge and exposes only echo publicly.
- hermes-stdio.yaml is the production-preferred Hermes config: it runs the Hermes tools MCP server as a stdio subprocess, exposes only skills_list publicly, and requires UAGENT_SEED.
- hermes-local.yaml is an in-process Hermes demo config (hermes-agent v0.16.x era) with the same policy.
- agentverse-mailbox.yaml is for manual hosted mailbox setup and requires UAGENT_SEED; see docs/agentverse-mailbox.md.

Run:

python -m hermes_fetch_ai.cli demo local
