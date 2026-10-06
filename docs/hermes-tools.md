# Letting other agents use Hermes' tools

Besides selling services and buying from other agents, the bridge can let agents on Fetch.ai's network call a small set of Hermes' tools that you choose. Each signed request is checked against a default-deny policy, replay protection, and argument checks; the tool runs in Hermes' tools server, a separate process; and the caller gets a size-capped result. Every decision goes to a redacted audit log.

```text
remote uAgent
   |  signed ListTools / CallTool messages (Fetch.ai's MCP message models)
   v
bridge uAgent (this package)
   |  rate limits, default-deny policy, replay protection,
   |  schema + URL/shell argument checks
   |  stdio subprocess with a filtered environment and timeouts
   v
Hermes tools MCP server (separate process)
   |
   v
size-capped response to the caller + redacted JSONL audit record
```

The bridge never touches Hermes' conversations and messaging surface. [`architecture.md`](architecture.md) has the trust boundaries and design decisions.

## Set it up

The bridge runs Hermes' tools MCP server as a stdio subprocess, with Hermes and the bridge in separate Python environments. With the plugin:

1. Install the bridge and give it a stable identity: `hermes fetchai-bridge install`, then `hermes fetchai-bridge setup` (or add `UAGENT_SEED`, at least 32 random characters, to `$HERMES_HOME/.env` yourself).
2. Get the example config, and leave `hermes_mcp.command` unset; the plugin hands the bridge Hermes' own interpreter:

   ```bash
   curl -fsSLo bridge.yaml https://raw.githubusercontent.com/ptanner66-prog/Hermes-Fetch-AI/main/examples/hermes-stdio.yaml
   ```

3. Check and run it:

   ```bash
   hermes fetchai-bridge probe-hermes      # expect: hermes_tools_server: importable
   hermes fetchai-bridge doctor --config bridge.yaml
   hermes fetchai-bridge serve --config bridge.yaml
   ```

Without the plugin, set `hermes_mcp.command` in `bridge.yaml` to the Python interpreter of the Hermes environment and run `hermes-fetch-ai doctor` / `hermes-fetch-ai serve` with the same arguments.

## What other agents can call

In this config only `skills_list` is public. It returns the name, description, and category of every installed skill, including skills you or the agent wrote, so remove it from `public_tools` if that is sensitive. Every other tool Hermes' tools server offers is denylisted. To give one agent more, list the tools for its address and remove them from `denied_tools` (the denylist always wins):

```yaml
policy:
  allowed_senders:
    agent1q...: [web_search]
```

Callers must follow each tool's input schema and attach replay-protection metadata; [`examples/call_bridge.py`](../examples/call_bridge.py) shows a complete client. If Hermes' tools server cannot start, `serve` exits with `hermes backend: FAIL` and names the command to run by hand to see why.

## Try it without Hermes

```bash
hermes-fetch-ai demo local      # expect: echo result: hello
hermes-fetch-ai serve --config examples/local-direct.yaml
python examples/call_bridge.py agent1q... http://127.0.0.1:8001/submit   # in another terminal
```

The demo runs a client uAgent and the bridge uAgent against fake tools, through the same policy path real calls use. [`demo.md`](demo.md) has more, including the Hermes-backed demo.

## Security defaults

- Tool calls are default-deny, and the denylist wins over any allowlist.
- A verified signature proves which agent address sent a message but grants nothing by itself: an address can call a tool only if the tool is in `public_tools` or listed for that address in `allowed_senders`.
- `ListTools` output is filtered, rate-limited, and size-capped.
- `CallTool` requires replay-protection metadata (a request ID and issue time) by default; duplicate, stale, or future-dated calls are rejected before the tool runs.
- Arguments are size-limited, schema-validated, and checked for unsupported URL schemes, private or local URL targets (including encoded IP forms and URLs inside longer text), and shell metacharacters.
- Tool responses are size-limited with deterministic truncation. They are **not** redacted; only expose tools whose output is safe for the caller.
- Audit records omit arguments, outputs, full sender addresses, seeds, tokens, and keys.
- With `publish_manifest: false` (the default), the bridge makes no outbound calls of its own: no Almanac registration, contract lookup, or status reports. Replying to a remote agent can look up that agent's endpoint in the Almanac.
- The bridge listens on all interfaces (`0.0.0.0`) on `agent.port`; uAgents has no bind-address setting, so firewall the port.

Residual risks are in [`security.md`](security.md).
