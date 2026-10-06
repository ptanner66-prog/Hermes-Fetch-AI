# Configuration

The bridge reads one YAML file (`--config`). Unknown keys are errors, and so are credential-shaped values: secrets come from the environment. [`src/hermes_fetch_ai/config.py`](../src/hermes_fetch_ai/config.py) is the source of truth for everything below; `hermes-fetch-ai doctor --config <file>` checks a file without starting anything.

The examples in [`examples/`](../examples) are complete configs: `local-direct.yaml` (fake tools), `hermes-stdio.yaml` (real Hermes tools, the production shape), `hermes-local.yaml` (Hermes in the same environment, v0.16.x only), `agentverse-mailbox.yaml` (manual, unverified), `paid-services.yaml` (selling services for testnet FET), and `asi-one.yaml` (selling them to ASI:One users through chat).

## `agent`

| Key | Default | Meaning |
|-----|---------|---------|
| `name` | `hermes_fetch_bridge` | The agent's name in logs. |
| `port` | `8000` | HTTP port. uAgents listens on all interfaces (`0.0.0.0`) and has no bind-address setting, so firewall the port. |
| `network` | `testnet` | `testnet` or `mainnet`: the Fetch network for the agent's address and the Almanac. Selling services needs `testnet`. |
| `mode` | `endpoint` | How remote agents reach the bridge: `endpoint` (directly, at `endpoint`), `mailbox` (through an Agentverse mailbox; manual and unverified), or `proxy` (through Agentverse's proxy; untested). |
| `endpoint` | none | The URL other agents use to reach the bridge, such as `https://bridge.example.com/submit`. Needed for Almanac registration. |
| `publish_manifest` | `false` | Register the bridge in the Almanac through Agentverse's API (free) and publish its protocol manifests. With `false` the bridge makes no outbound calls of its own. |
| `ledger_registration` | `false` | With `publish_manifest`, also register on the Almanac contract on the Fetch ledger, which spends fees from the agent's wallet. Off, the bridge never looks the contract up and never spends on its own. |
| `enable_agent_inspector` | `false` | uAgents' Agent Inspector. Its `/connect` and `/disconnect` endpoints are unauthenticated; enable it only while connecting a mailbox. |
| `dev_random_seed` | `false` | Use a new random identity on every start, for demos. With `false`, `UAGENT_SEED` is required. |
| `description` | `Hermes Fetch AI bridge` | Shown in the published manifest and on Agentverse. |
| `handle` | none | The agent's handle on Agentverse, which ASI:One users can write as `@handle`: lowercase letters, digits, `-` and `_`, 3 to 20 characters. Used by `agentverse register`. |
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

## `payments`

How buyers pay for services ([`payments.md`](payments.md)). Fetch's testnet only.

| Key | Default | Meaning |
|-----|---------|---------|
| `enabled` | `false` | Sell the services under `services`. Needs `agent.network: testnet`. A selling bridge handles each incoming message in its own task, so a long run never holds up other requests. |
| `network` | `testnet` | The only accepted value; `mainnet` is locked until a security review. |
| `chain_id` | `dorado-1` | The testnet chain. The bridge checks that the ledger reports it before verifying any payment, and refuses payments otherwise. |
| `denom` | `atestfet` | The testnet unit: 1 FET = 10^18 `atestfet`. |
| `ledger_url` | `https://rest-dorado.fetch.ai` | The Cosmos REST endpoint the bridge reads transactions from. `https://`, or `http://` on this machine only; no credentials or query. |
| `ledger_timeout_seconds` | `8` | Limit for one ledger lookup, retries included. |
| `payout_address` | the agent's wallet | The `fetch1...` wallet buyers pay. Unset, it is the wallet derived from `UAGENT_SEED` (key index 0). Required with `agent.dev_random_seed: true`, whose wallet changes on every start. |
| `state_dir` | per platform | Where payment records live, in a folder per agent address: `$XDG_STATE_HOME/hermes-fetch-ai` (`~/.local/state/...` when unset) on Linux and macOS, `%LOCALAPPDATA%\HermesFetchAI` on Windows. `~` is expanded. |
| `quote_ttl_seconds` | `600` | How long a price quote can be paid. |
| `redeem_window_seconds` | `86400` | How long after a quote expires its payment can still be presented, and how long a verified payment stays usable before it lapses. |
| `max_attempts` | `3` | Runs a paid request gets when the service fails on the seller's side; after that the payment is `failed` and needs a refund. |
| `max_verifications_per_minute_per_sender` | `6` | Ledger lookups one buyer can cause per minute. |
| `max_global_verifications_per_minute` | `60` | Ledger lookups all buyers together can cause per minute. |

## `services`

The services this agent sells, by name: `services: {<name>: {...}}`. Each appears to other agents as the tool `service.<name>`, with one string argument, `request`. Names use lowercase letters, digits, `_` and `-`, start with a letter or digit, and are at most 40 characters. Services need `payments.enabled: true`.

| Key | Default | Meaning |
|-----|---------|---------|
| `title` | required | A short name buyers see, up to 80 characters. |
| `description` | required | What the service does, up to 500 characters. |
| `price` | `"0"` | Testnet FET per request, as a string (`"0.05"`): up to 18 decimal places, at most 1000. `"0"` is free. |
| `input.max_chars` | `4000` | Longest request accepted. |
| `input.check_urls` | `true` | Reject requests that contain URLs to local or private addresses. Turn it off only for a service that never fetches anything, such as a code review. |
| `runner` | required | What does the work: `{type: command, ...}` or `{type: hermes, ...}` (below), or `{type: echo}`, which answers with the request (demos and tests). |
| `disclaimer` | none | Added to the end of every answer, up to 500 characters. |
| `max_runs_per_day` | `200` | Runs per 24 hours across all buyers. |
| `max_running` | `1` | Requests the service works on at once. |
| `max_waiting` | `4` | Requests that may wait for a run. Beyond that, buyers are told the service is busy before they pay. |

A `command` runner:

| Key | Default | Meaning |
|-----|---------|---------|
| `argv` | required | The program and its arguments, as a list. The program must be an absolute path; no shell is used. |
| `timeout_seconds` | `300` | The program is stopped after this long, and the run counts as a failure on the seller's side. |
| `max_output_chars` | `20000` | Longer answers are cut off with a note. |
| `pass_env` | `[]` | Names of environment variables the program may see, besides a short fixed list. Values never go in the config. |

A `hermes` runner (a guest Hermes, [guest-hermes.md](guest-hermes.md)):

| Key | Default | Meaning |
|-----|---------|---------|
| `model` | required | The model, as the provider names it. |
| `provider` | Hermes picks | Hermes' provider name, such as `openrouter` or `custom`. |
| `base_url` | none | The model server's `http(s)://` address, for `provider: custom`. |
| `toolsets` | `[]` | `[web]` or nothing; no other toolset is accepted. |
| `instructions` | a generic line | What the guest is told about the job, up to 8000 characters. |
| `max_turns` | `8` | Most tool-using steps per request, 1 to 50. |
| `timeout_seconds` | `300` | The guest is stopped after this long, and the run counts as a failure on the seller's side. |
| `max_output_chars` | `20000` | Longer answers are cut off with a note. |
| `env_file` | `guests/<name>.env` in the state folder | The guest's keys file (its model key, and a web search key if any). Must be private (`chmod 600`) and set no `HERMES_...` variable. |
| `pass_env` | `[]` | Names of environment variables the guest may see, such as `HTTPS_PROXY`; no `HERMES_...` names. |
| `python` | from `hermes fetchai-bridge` | The Python Hermes runs on, as an absolute path. |

`doctor` and `serve` fail if a program, or a file named by absolute path in `argv`, does not exist, or if a guest Hermes could not run safely, so the bridge never takes payments for a service that cannot run. `doctor` also names each guest's keys file. `seller try` runs a service once without payment.

## `chat`

| Key | Default | Meaning |
|-----|---------|---------|
| `enable_chat` | `false` | Sell the services under `services` through Fetch's chat protocol, in plain language, to ASI:One users and other chat agents ([`asi-one.md`](asi-one.md)). Needs at least one service. Chat reaches only the services, never Hermes' tools. |

## `buying`

Hermes buying from other agents ([`buying.md`](buying.md)). Testnet only; needs a stable `UAGENT_SEED`, because the buying wallet comes from it (key index 1, never the income wallet). Ledger settings come from `payments` (`ledger_url`, `chain_id`, `denom`), whether or not `payments.enabled` is set.

| Key | Default | Meaning |
|-----|---------|---------|
| `enabled` | `false` | Run the buyer inside `serve`, with its control channel for `buyer` commands and the plugin's tools. |
| `max_payment` | `"1"` | Most one payment may be, in testnet FET. |
| `max_per_seller_per_day` | `"2"` | Most paid to one agent in any 24 hours. |
| `max_per_day` | `"5"` | Most paid in any 24 hours, to all agents. Must be at least the other two. |
| `allowed_sellers` | `[]` | Agent addresses (`agent1...`) Hermes may pay; empty means any agent. |
| `reply_wait_seconds` | `60` | How long sending a message, or paying, waits for the other agent's answer, up to 600. Later replies wait in the bridge for `buyer inbox` and Hermes' `fetchai_read_replies`. |
| `max_message_chars` | `4000` | Longest message Hermes may send, up to 50,000. |

Payments that may have left the wallet (sent, paid, unknown, confirmed, or cancelled after paying) count against the limits; refused and failed ones do not.

## Environment

| Variable | Used for |
|----------|----------|
| `UAGENT_SEED` | The bridge's identity and wallet key, at least 32 random characters. Required unless `agent.dev_random_seed` is `true`. Never put it in YAML. |
| `HERMES_HOME` | Passed to Hermes' tools server, so it uses the right Hermes home. |
| `HERMES_FETCH_AI_HERMES_PYTHON`, `HERMES_FETCH_AI_HERMES_PYTHONPATH` | Set by the Hermes plugin: Hermes' interpreter and import path, used when `hermes_mcp.command` is unset. |
| `AGENTVERSE_API_KEY` | Only for `agentverse register`: an Agentverse API key with write access. Through Hermes, the plugin's "Agentverse API key" setting. |

The bridge does not read `.env` files. Through `hermes fetchai-bridge`, Hermes loads `$HERMES_HOME/.env` and the plugin passes `UAGENT_SEED` on; under systemd, use an `EnvironmentFile` ([`production.md`](production.md)).
