# Examples

| File | What it is |
|------|------------|
| `local-direct.yaml` | A bridge with the two built-in fake tools; only `echo` is public. No Hermes, no secrets, and a new random identity on every start. `demo local` uses it. |
| `hermes-stdio.yaml` | The production shape: Hermes' tools MCP server as a stdio subprocess, only `skills_list` public, every other tool denylisted, and a stable identity from `UAGENT_SEED`. Through `hermes fetchai-bridge`, leave `hermes_mcp.command` unset; when running `hermes-fetch-ai` directly, set it to the Python interpreter of the Hermes environment. |
| `hermes-local.yaml` | The same policy with Hermes' tools server imported into the bridge's process. Works only with hermes-agent v0.16.x, which could share the bridge's environment. |
| `agentverse-mailbox.yaml` | For a manual Agentverse mailbox setup; needs `UAGENT_SEED`. See [`docs/agentverse-mailbox.md`](../docs/agentverse-mailbox.md). |
| `call_bridge.py` | A client that lists a running bridge's tools and calls one, with replay-protection metadata. |

Try the fake-tools bridge over HTTP:

```bash
hermes-fetch-ai serve --config examples/local-direct.yaml
# logs: Starting agent with address: agent1q...

# in another terminal
python examples/call_bridge.py agent1q... http://127.0.0.1:8001/submit
```

Or run both sides in one process, with no HTTP:

```bash
hermes-fetch-ai demo local
```

Every setting is described in [`docs/configuration.md`](../docs/configuration.md).
