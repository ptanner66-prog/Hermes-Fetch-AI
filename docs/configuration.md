# Configuration

The bridge reads one YAML file (`--config`). Unknown keys are errors, and so are credential-shaped values: secrets come from the environment. [`src/hermes_fetch_ai/config.py`](../src/hermes_fetch_ai/config.py) is the source of truth for everything below; `hermes-fetch-ai doctor --config <file>` checks a file without starting anything.

The examples in [`examples/`](../examples) are complete configs: `local-direct.yaml` (fake tools), `hermes-stdio.yaml` (real Hermes tools, the production shape), `hermes-local.yaml` (Hermes in the same environment, v0.16.x only), and `agentverse-mailbox.yaml` (manual, unverified).

## `agent`

| Key | Default | Meaning |
|-----|---------|---------|
| `name` | `hermes_fetch_bridge` | The agent's name in logs. |
| `port` | `8000` | HTTP port. uAgents listens on all interfaces (`0.0.0.0`) and has no bind-address setting, so firewall the port. |
| `network` | `testnet` | `testnet` or `mainnet`: the Fetch network for the agent's address and the Almanac. |
| `mode` | `endpoint` | How remote agents reach the bridge: `endpoint` (directly, at `endpoint`), `mailbox` (through an Agentverse mailbox; manual and unverified), or `proxy` (through Agentverse's proxy; untested). |
| `endpoint` | none | The URL other agents use to reach the bridge, such as `https://bridge.example.com/submit`. Needed for Almanac registration. |
| `publish_manifest` | `false` | Register the bridge in the Almanac and publish its protocol manifest. With `false` the bridge makes no outbound calls of its own; with `true`, registration can spend fees from the agent's wallet. |
| `enable_agent_inspector` | `false` | uAgents' Agent Inspector. Its `/connect` and `/disconnect` endpoints are unauthenticated; enable it only while connecting a mailbox. |
| `dev_random_seed` | `false` | Use a new random identity on every start, for demos. With `false`, `UAGENT_SEED` is required. |
| `description` | `Hermes Fetch AI bridge` | Shown in the published manifest. |
| `seed` | | Always rejected: the seed comes only from `UAGENT_SEED`. |

## `hermes_mcp`

| Key | Default | Meaning |
|-----|---------|---------|
| `mode` | `fake` | `fake` (two built-in demo tools), `stdio` (run Hermes' tools MCP server as a child process), or `in_process_hermes_tools` (import it into the bridge's process; works only with hermes-agent v0.16.x). |
| `command` | none | For `stdio`: the program to run, normally the Python interpreter of the Hermes environment. Through `hermes fetchai-bridge`, leave it unset and the plugin supplies Hermes' interpreter. |
| `args` | `[]` | The program's arguments. The Hermes examples use `["-m", "agent.transports.hermes_tools_mcp_server"]`, which is also the default when `command` comes from the plugin. |
| `timeout_seconds` | `10` | Limit for server startup, for each `ListTools`/`CallTool` round trip to the server, and for a call's argument checks (which may resolve DNS). |

## `policy`

| Key | Default | Meaning |
|-----|---------|---------|
| `public_tools` | `[]` | Tools every sender may list and call. |
| `allowed_senders` | `{}` | Extra tools per agent address, as `agent1q...: [tool, ...]`. |
| `denied_tools` | `[]` | Tools never exposed to anyone. The denylist wins over the other two. |
| `trusted_shell_tools` | `[]` | Tools whose string arguments may contain shell metacharacters, control characters, and query strings. URL checks still apply. List a tool only if it never passes arguments to a shell. |
| `max_args_bytes` | `65536` | Largest accepted call arguments, as JSON. |
| `max_output_bytes` | `65536` | Tool results longer than this are truncated, with a marker that gives the original size. |
| `max_list_tools_response_bytes` | `65536` | A tool list larger than this is returned empty, with the error `response too large`. |
| `max_calls_per_minute_per_sender` | `30` | `CallTool` limit per sender. `0` blocks calls. |
| `max_list_tools_per_minute_per_sender` | `30` | `ListTools` limit per sender. `0` blocks listing. |
| `max_global_calls_per_minute` | `300` | `CallTool` limit across all senders. Requests a sender's own limit rejects do not count. |
| `max_global_list_tools_per_minute` | `300` | `ListTools` limit across all senders. |
| `max_tracked_senders` | `4096` | Senders tracked for rate limiting; the least recently seen are forgotten first. |
| `require_replay_metadata` | `true` | Require a request ID and issue time on every call. Calls without them get no replay protection, so keep this on. |
| `replay_ttl_seconds` | `300` | How old a call's issue time may be. |
| `max_replay_clock_skew_seconds` | `60` | How far in the future a call's issue time may be. |
| `max_replay_entries` | `8192` | Request IDs remembered for replay detection. The cache is in memory, so a restart clears it. |

Tool names in these lists may contain only letters, digits, `_`, `.` and `-`, up to 128 characters; anything else is a config error.

## `logging`

| Key | Default | Meaning |
|-----|---------|---------|
| `audit_path` | per platform | The JSONL audit log. Default: `$XDG_STATE_HOME/hermes-fetch-ai/audit.jsonl` (`~/.local/state/...` when unset) on Linux and macOS, `%LOCALAPPDATA%\HermesFetchAI\audit.jsonl` on Windows. `~` is expanded. The file rotates at 25 MB and keeps five old files. |

## `chat`

| Key | Default | Meaning |
|-----|---------|---------|
| `enable_chat` | `false` | Must stay `false`: the chat protocol is out of scope. |

## Environment

| Variable | Used for |
|----------|----------|
| `UAGENT_SEED` | The bridge's identity and wallet key, at least 32 random characters. Required unless `agent.dev_random_seed` is `true`. Never put it in YAML. |
| `HERMES_HOME` | Passed to Hermes' tools server, so it uses the right Hermes home. |
| `HERMES_FETCH_AI_HERMES_PYTHON`, `HERMES_FETCH_AI_HERMES_PYTHONPATH` | Set by the Hermes plugin: Hermes' interpreter and import path, used when `hermes_mcp.command` is unset. |

The bridge does not read `.env` files. Through `hermes fetchai-bridge`, Hermes loads `$HERMES_HOME/.env` and the plugin passes `UAGENT_SEED` on; under systemd, use an `EnvironmentFile` ([`production.md`](production.md)).
