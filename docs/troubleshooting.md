# Troubleshooting

Messages are grouped by where they appear. A remote caller sees a short reason in the `error` field of `ListToolsResponse` or `CallToolResponse`; the audit log records the same text as `reason`, and details the caller should not see go to the bridge's log.

## Installing and the Hermes plugin

### `fetchai-bridge: 'hermes-fetch-ai' not found`

The plugin could not find the bridge. Install it in its own environment:

```bash
uv tool install --python 3.12 "hermes-fetch-ai @ git+https://github.com/ptanner66-prog/Hermes-Fetch-AI"
```

or set `plugins.entries.fetchai-bridge.settings.command` to the full path of `hermes-fetch-ai`. Do not install the bridge into Hermes' environment: the two pin different `mcp` versions.

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

## Windows

Use an absolute path for `hermes_mcp.command`, and quote paths that contain spaces. To find Hermes' interpreter, run `Get-Command hermes` in PowerShell (`where` means `Where-Object` there). The bridge passes child processes only an environment allowlist that includes the Windows essentials, and keeps their stderr away from the protocol stream.
