# Troubleshooting

Messages are grouped by where they appear. A remote caller sees a short reason in the `error` field of `ListToolsResponse` or `CallToolResponse`; the audit log records the same text as `reason`, and details the caller should not see go to the bridge's log.

## Installing and the Hermes plugin

### `fetchai-bridge: 'hermes-fetch-ai' not found`

The plugin could not find the bridge. Install it, in its own environment:

```bash
hermes fetchai-bridge install
```

or set `plugins.entries.fetchai-bridge.settings.command` to the full path of `hermes-fetch-ai`. Do not install the bridge into Hermes' environment: the two pin different `mcp` versions.

### `install` says to install uv first

`install` uses [uv](https://docs.astral.sh/uv/getting-started/installation/) (or pipx). Install uv with the one command on that page, open a new terminal, and run `hermes fetchai-bridge install` again.

### `Installed, but your terminal cannot find hermes-fetch-ai yet`

The installer put the bridge in a folder your terminal does not search yet. Run the command the message names (`uv tool update-shell`, or `pipx ensurepath` after a pipx install), open a new terminal, and go on with `hermes fetchai-bridge setup`. Running `install` or `setup` again before that only repeats the install.

### The install fails at `git+https://...@v<version>`

The bridge is installed from the git tag of the plugin's version. If that tag does not exist yet (an unreleased plugin), install the bridge from the branch you got the plugin from, for example `uv tool install --force --python 3.12 "hermes-fetch-ai @ git+https://github.com/ptanner66-prog/Hermes-Fetch-AI@main"`.

### `note: this bridge is version X and the fetchai-bridge plugin is Y`

The plugin and the bridge come from different releases. `hermes fetchai-bridge install` installs the bridge that matches the plugin.

### `Hermes did not keep it, so nothing was set up`

`setup` keeps the agent's key in Hermes' `.env` through Hermes itself, and this Hermes did not save it (for example, a managed install whose `.env` is read-only). Set the "uAgent seed" in the plugin's settings (at least 32 random characters; `python -c "import secrets; print(secrets.token_hex(32))"` makes one), then run setup again.

### `setup asks questions; run it in a terminal`

Setup was run where nobody can answer (a script, or Hermes' own tools). Run `hermes fetchai-bridge setup` in a terminal yourself.

### `config: FAIL: no config yet; run hermes fetchai-bridge setup`

The commands use the config setup writes. Run `hermes fetchai-bridge setup`, or pass `--config <file>` for a config of your own.

## Running in the background

### `Your agent could not start`

`start` shows the end of the agent's log. The usual causes, by what the log says:
- `address already in use`: another program uses the agent's port. Run setup again (it picks a free port), then `start`.
- `services: FAIL: ...`: see "Selling services" below.
- `UAGENT_SEED is required`: start the agent through Hermes (`hermes fetchai-bridge start`), which passes the key from Hermes' `.env`.

### `serve: FAIL: another bridge is already running with these records`

An agent is already running with the same records folder (perhaps started with `start` in another terminal). `hermes fetchai-bridge status` shows it; stop it with `hermes fetchai-bridge stop` before starting another.

### `Your agent did not stop within 40 seconds; stopping it now`

The agent was busy and did not finish in time, so `stop` ended it. A payment it was sending is marked `needs_review` the next time it starts; run `hermes fetchai-bridge buyer check <id>` for it, as `status` says.

### `status` says `Testnet: not answering`

The bridge could not reach Fetch's testnet ledger (`payments.ledger_url`), so it shows no balances. Your agent may still be running fine; check your internet connection, or run `status --offline`.

### `Testnet: its newest block is ... old; the chain may have stopped`

Fetch's test network has stopped making blocks for now. Payments wait until it moves again; nothing is lost.

### ``hermes: 'fetchai-bridge' is not a `hermes` command``

Hermes did not load the plugin's command. Check that the plugin is installed and enabled (`hermes plugins list`; enable it with `hermes plugins enable fetchai-bridge`). Hermes builds that run plugins with `plugins.isolation: host` (on `main` after 0.21.5) skip plugin CLI commands; there, [run the bridge directly](hermes-plugin.md#running-without-the-plugin).

### `hermes fetchai-bridge --version` prints Hermes' version

Hermes handles a leading `--version` itself. `hermes fetchai-bridge doctor` prints the bridge's version on its first line.

### `hermes_tools_server: not importable`

`probe-hermes` exits with status 1 when the bridge cannot import Hermes' tools server.

- Run directly as `hermes-fetch-ai probe-hermes`, this is expected (`hermes_python: not handed over`): the bridge checks its own environment, which does not contain Hermes. Run `hermes fetchai-bridge probe-hermes` instead.
- Through the plugin, Hermes' own interpreter could not import `agent.transports.hermes_tools_mcp_server`. Hermes needs its `mcp` extra (included in `[all]`). When installing Hermes from a checkout, use the Python version in its `.python-version`; on an older Python, the install appears to succeed but skips Hermes' dependencies.

## Config errors (`doctor`, `serve`)

`doctor` and `serve` print `config: FAIL: <setting>: <problem>` to stderr and exit with status 1. They never echo the value that failed. Every setting is described in [`configuration.md`](configuration.md).

### `Extra inputs are not permitted`

The config has a key the bridge does not know, often a typo. The bridge rejects unknown keys rather than ignoring them.

### `hermes_mcp.command is required for stdio mode ...`

The config uses `mode: stdio` without `command`, and the bridge was not started by the Hermes plugin. Run it as `hermes fetchai-bridge serve --config ...` (the plugin supplies Hermes' interpreter), or set `hermes_mcp.command` to the Python interpreter of the environment where `hermes-agent` is installed.

### `UAGENT_SEED is required when agent.dev_random_seed=false`

The config asks for a stable identity, and `UAGENT_SEED` is not set. Set it in the environment, or in `$HERMES_HOME/.env` when running through the plugin. Never put it in YAML.

### `UAGENT_SEED must be at least 32 characters`

The agent's signing key is derived from the seed, so short seeds are rejected. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"`.

### `secret-shaped YAML values are not allowed`

The config contains something that looks like a credential: a bearer token, an `sk-`/`pk-` key, a JWT, a long hex string, an assignment such as `token=...`, a non-empty value under a key named like a secret, or a flag such as `--api-key` in `hermes_mcp.args`. Pass secrets through the environment.

### `'<name>' is not a valid tool name`

A tool name in `policy` has characters other than letters, digits, `_`, `.` and `-`, or is longer than 128 characters. Use the exact names `ListTools` returns.

### `seed: WARN: UAGENT_SEED is set but agent.dev_random_seed is true ...`

A warning, not an error: with `dev_random_seed: true`, `UAGENT_SEED` is ignored and the bridge gets a new address on every start. Set `agent.dev_random_seed: false` for a stable identity.

### `pins: WARN: ...`

An installed dependency differs from the version this release was tested with. Reinstall the bridge in a clean environment (`uv tool install --reinstall ...`).

## `serve` fails at startup

### `hermes backend: FAIL`

`serve` could not start Hermes' tools MCP server and exited with status 1. The message says why:

- `command not found`: `hermes_mcp.command` does not exist. Use the absolute path to the Python interpreter of the environment where `hermes-agent` is installed.
- `McpError: Connection closed`: the server exited during startup, usually because `agent.transports.hermes_tools_mcp_server` does not import in that environment (see [`not importable`](#hermes_tools_server-not-importable)).
- `timed out`: the server did not finish starting within `hermes_mcp.timeout_seconds`. Importing Hermes can take several seconds on a cold start; raise the timeout if it only fails the first time.

The server's stderr is discarded on purpose, because it is outside the bridge's redaction. The message names the command to run by hand to see the error, for example `/path/to/hermes-venv/bin/python -m agent.transports.hermes_tools_mcp_server`.

### `serve: FAIL: the bridge's HTTP server stopped during startup ...`

Usually `agent.port` is already in use; the error logged just above says. Stop the other process or change `agent.port`.

## Errors remote callers see

### `rate limit exceeded`, `global rate limit exceeded`

The sender, or all senders together, used up the minute's budget for that request type (`policy.max_*_per_minute*`). A request denied by one limit does not count against the other. A limit of 0 blocks that request type.

### `tool not allowed for sender`, `tool denied`

The tool is neither public nor allowlisted for this sender, or it is on the denylist, which always wins. To grant it, add the exact name to `policy.public_tools`, or to the sender's entry in `policy.allowed_senders`.

### `unknown tool`

The policy allows the tool, but the backend does not serve it. Hermes' tools server never serves `terminal` or the file tools, and serves the others only when their requirements are met in that Hermes install (for example, `image_generate` needs an image-generation backend).

### `missing replay metadata`, `invalid replay metadata`

`CallTool` must carry replay-protection metadata under the reserved argument key `_hermes_fetch_ai`, with a fresh `request_id` (8 to 128 characters from `A-Z a-z 0-9 _ . : -`) and `issued_at_ms`, and no other keys. The rules are in [`production.md`](production.md#replay-protection-contract); [`examples/call_bridge.py`](../examples/call_bridge.py) shows a client that sends it.

### `stale replay metadata`, `future replay metadata`

`issued_at_ms` is older than `policy.replay_ttl_seconds` (default 300) or further ahead than `policy.max_replay_clock_skew_seconds` (default 60). Check the client's clock, and stamp each call when it is sent.

### `replay detected`

The sender already used this request ID for a call that reached the tool. That covers retries: if a call timed out on the client side, the tool may still have run, so treat the first attempt as final rather than retrying with the same ID. A call denied before it reaches the tool does not use up its ID.

### `schema validation failed`

The arguments do not match the tool's input schema from `ListTools`. Follow the served schema: hermes-agent v0.16.x wrapped arguments in one `kwargs` object, and newer releases take them flat.

### `shell metacharacters or control characters are not allowed`

An argument contains `;`, `&`, `|`, `$`, `<`, `>`, a backslash, a backtick, or a control character such as a newline. That includes URLs whose query string has `&` and multi-line text. If a tool never passes its arguments to a shell, add its exact name to `policy.trusted_shell_tools`; URL checks still apply to it.

### URL errors

Every string in the arguments is checked for URLs, including URLs embedded in text and bare hosts such as `localhost:8080`:

- `URL targets private or local address`, `URL resolves to private or local address`: the URL points at a loopback, private, link-local, or otherwise non-public address, written directly, in an encoded form such as `0x7f000001`, or by a name that resolves to one. These are rejected on purpose.
- `unsupported URL scheme`: only `http` and `https` are allowed.
- `URL host is required`, `URL host could not be resolved`: the URL has no host, or DNS has no answer for it.
- `URL must not contain backslashes, whitespace, or control characters`: URL parsers disagree about these, so a URL that contains one could reach a different host than the one checked.
- `too many URL hosts in one call`: one call may name at most 16 different hosts.

### `argument checks timed out`

The URL checks' DNS lookups took longer than `hermes_mcp.timeout_seconds`. Check the bridge host's DNS.

### `unsafe tool name`, `tool name too long`, `args exceed max_args_bytes`, `tool args must be an object`

The request is malformed or oversized. Tool names use letters, digits, `_`, `.` and `-` (at most 128 characters); `policy.max_args_bytes` caps the arguments' JSON size.

### `response too large`

The tool list for this sender is larger than `policy.max_list_tools_response_bytes`, so it is withheld. Raise the limit or make fewer tools visible.

### `backend unavailable`

The Hermes backend stopped responding after startup. The audit record has `decision: error`, and the bridge's log names the exception. Restart the bridge; systemd's `Restart=on-failure` does not fire while the process is still running.

### `timeout`

The tool did not answer within `hermes_mcp.timeout_seconds`. It may still have run, and its request ID is used up. Raise the timeout for slow tools.

### `tool call failed`

The connection to the tools server failed during the call. The bridge's log has the exception. Other error text in `error` comes from the tool itself.

### `internal bridge error`

An unexpected exception in the bridge. The traceback is in the bridge's log with the audit record's `trace_id`. Please [report it](https://github.com/ptanner66-prog/Hermes-Fetch-AI/issues) if it repeats.

## Selling services

The errors buyers can get are listed in [`payments.md`](payments.md#errors-a-buyer-can-get). These are the ones you see.

### `services: FAIL: service <name>: program <path> not found`

`doctor`, `serve`, or `seller try` could not find a service's program, or a file named by absolute path in its `argv`. The bridge refuses to start rather than take payments for a service that cannot run. Fix the path; `which python3` (or `Get-Command python` on Windows) prints the interpreter's full path.

### `services: FAIL: service <name>: program <path> is not executable`

Make it executable (`chmod +x <path>`), or put the interpreter first: `argv: [/usr/bin/python3, /path/to/program.py]`.

### `services: FAIL: service <name>: Hermes' Python is unknown ...`

The service runs a guest Hermes, and the bridge does not know which Python Hermes runs on. Run the bridge through Hermes (`hermes fetchai-bridge ...`), which hands it over, or set the runner's `python`. On Linux and macOS, `head -1 "$(command -v hermes)"` prints it after the `#!`.

### `services: FAIL: service <name>: Hermes is not installed for <python>`

That Python cannot import Hermes. Point `python` at the interpreter of the environment Hermes was installed into.

### `services: FAIL: service <name>: <file> sets ..., which would change how the guest Hermes behaves or where it sends requests ...`

A `.env` file that Hermes loads into guests sets a variable that changes Hermes' own behavior, such as `HERMES_ALLOW_PRIVATE_URLS`, or where it sends requests, such as `CUSTOM_BASE_URL` or `OPENROUTER_BASE_URL`. The file is the guest's keys file, the `.env` in Hermes' install folder, or `/etc/hermes/.env`. Remove those lines; a guest's keys file holds only model and web search keys, and its model's address is the runner's `base_url`.

### `services: FAIL: service <name>: <file> holds keys but others can read it ...`

Make the guest's keys file private: `chmod 600 <file>`.

### `seller: FAIL: <name>: the guest Hermes gave no answer ...` or `... could not finish`

Hermes ran but produced no clean answer. `seller try` shows Hermes' own messages above this line; the usual causes are a missing or wrong key in the guest's keys file (`doctor` names it), a model name the provider does not know, or a provider account without credit. See [`guest-hermes.md`](guest-hermes.md).

### `seller: FAIL: <name>: the service took too long`

The service ran past its `timeout_seconds`. For a guest Hermes this often means the model server does not answer: Hermes keeps retrying, and the bridge stops it at the limit. Check the provider, or raise `timeout_seconds` for slow models.

### `the program (argv[0]) must be an absolute path, such as ...`

Programs are given as full paths, so the bridge never depends on `PATH` to find them. Use the path the message suggests, if it is the program you mean.

### `payments run on Fetch's testnet only ...`

`payments.network` or `agent.network` is not `testnet`. Mainnet is locked in this version.

### `payout_address must be a fetch1... wallet address`

The address is mistyped or is not a Fetch wallet address. Leave it unset to receive payments in the agent's own wallet.

### `seller: FAIL: this config has agent.dev_random_seed: true ...`

`wallet` and `seller` need a stable identity, because the payment records and the wallet belong to one seed. Set `agent.dev_random_seed: false` and set `UAGENT_SEED`.

### `ledger: FAIL: ...`

`hermes-fetch-ai ledger --config <file>` could not reach `payments.ledger_url`, or the endpoint is not Fetch's testnet. Check your network, or wait if Fetch's endpoint is down; buyers get `payment pending` meanwhile and can retry.

### `agentverse: FAIL: ...`

Listing the bridge for ASI:One users: see the table of problems in [`asi-one.md`](asi-one.md#problems).

### A service keeps failing (`decision: error` in the audit log)

Run it by hand with `hermes-fetch-ai seller try <service> --request "..." --config <file>`, which shows the program's error output. Buyers keep their payment for a retry; after `payments.max_attempts` failures it is listed as `failed` by `seller credits` and needs a refund.

## Buying from other agents

[`buying.md`](buying.md) explains the states a payment goes through.

### `buyer ...: FAIL: your agent is not running with buying on ...`

The `buyer` commands (and Hermes' buying tools) work through your running agent. Start it with `hermes fetchai-bridge start`. If `status` says Hermes may not buy, run `hermes fetchai-bridge setup` and say yes to buying (it sets `buying.enabled: true`), then `hermes fetchai-bridge restart`. If you run the bridge with a config of your own that sets `payments.state_dir`, pass the same `--config` to the `buyer` commands (or set the plugin's "Bridge config" setting).

### `buyer ...: FAIL: the bridge is not answering ...`

`control.json` is left from a bridge that stopped without cleaning up. Start the bridge again; it replaces the file.

### `serve` fails with `another bridge is already buying with the records in ...`

Another `serve` with buying on is using the same state folder. Stop it, or give this bridge its own `payments.state_dir`.

### Hermes says `Turn off YOLO mode to work with other agents`

The buying tools refuse while YOLO mode is on (`--yolo`, `/yolo`, `HERMES_YOLO_MODE`, or `approvals.mode: off`). Turn it off to work with other agents: type `/yolo` again in the session, or start Hermes without `--yolo`. If it is on from the start, remove `HERMES_YOLO_MODE` from your environment or Hermes' `.env`, or set `approvals.mode` back to its default in Hermes' settings.

### Hermes says `this Hermes cannot ask you to approve a payment ...`

This Hermes has no confirmation prompt the plugin can use, so Hermes will not pay. Pay from a terminal instead: `hermes fetchai-bridge buyer show <id>`, then the `buyer pay` command it prints.

### `buyer pay: FAIL: ...`

| Message | What to do |
|---------|------------|
| `this approval does not match the payment request shown` | Run `buyer show <id>` again and use the new code; each `show` makes a new one, and each code pays once. |
| `the amount differs ...`, `the recipient differs ...` | Copy them exactly as `show` printed them. |
| `... would go over the daily limit ...` | Wait, or raise `buying.max_per_day` (or the per-seller limit) in your config and restart the bridge. |
| `the amount is more than the limit for one payment` | Raise `buying.max_payment`, if you meant to. |
| `this seller is not on the list of agents Hermes may pay` | Add it to `buying.allowed_sellers`, if you trust it. |
| `this payment request has expired; ask the seller again` | Ask the seller for a new payment request. |

A payment shown as `failed` with `could not prepare the payment` usually means the buying wallet has no test FET: run `wallet --config <your config> --fund`.

### Hermes paid, but the seller's answer has not come

Some work takes minutes. Paying waits for the answer as long as `buying.reply_wait_seconds` (60 seconds by default); after that the answer waits in the bridge. Hermes reads it with `fetchai_read_replies`; from a terminal, `hermes-fetch-ai buyer inbox --agent <agent> --session <conversation> --wait 120` waits for it. If the seller cancelled after you paid, the payment shows as `cancelled`: ask the seller for a refund.

### `buyer ...: FAIL: the bridge stopped before it answered ...`

The bridge was stopped while it worked on the request. On a stop, requests waiting for replies answer at once with what they have, and a payment being sent gets 20 seconds to finish. Run `hermes-fetch-ai buyer purchases`: a payment that was still being sent shows as `needs_review` (see below).

### A payment is `needs_review`

The bridge could not tell whether it went through, or was stopped while sending it. It is never resent on its own. Run `hermes-fetch-ai buyer check <id>`: it looks the payment up on the ledger and marks it paid (and tells the seller) or failed. A payment that never appears is marked failed after an hour.

## Windows

Use an absolute path for `hermes_mcp.command`, and quote paths that contain spaces. To find Hermes' interpreter, run `Get-Command hermes` in PowerShell (`where` means `Where-Object` there). The bridge passes child processes only an environment allowlist that includes the Windows essentials, and keeps their stderr away from the protocol stream.
