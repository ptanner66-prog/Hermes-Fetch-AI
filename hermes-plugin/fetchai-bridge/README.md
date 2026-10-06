# fetchai-bridge

A Hermes plugin for [Hermes Fetch AI](https://github.com/ptanner66-prog/Hermes-Fetch-AI), a bridge that lets agents on Fetch.ai's network (uAgents) call a small, explicitly allowed set of Hermes tools, with a default-deny policy, replay protection, argument checks, and a redacted audit log.

The bridge pins its own dependencies (uAgents, mcp 1.28.1) and runs on Python 3.11/3.12, so it cannot share Hermes' environment. This plugin is a thin, stdlib-only wrapper (`python_runtime: external`): it adds a `hermes fetchai-bridge` command that runs the separately installed bridge, and it ships an `operate` skill for the agent.

Requires Hermes 0.21.5 or later; CI tests 0.21.5 and a pinned `main`. Hermes Fetch AI is an independent community project, not affiliated with or endorsed by Fetch.ai or Nous Research.

## Install

1. Install the bridge in its own environment:

   ```bash
   uv tool install --python 3.12 "hermes-fetch-ai @ git+https://github.com/ptanner66-prog/Hermes-Fetch-AI"
   ```

2. Install and enable the plugin:

   ```bash
   hermes plugins install ptanner66-prog/Hermes-Fetch-AI/hermes-plugin/fetchai-bridge
   hermes plugins enable fetchai-bridge
   ```

3. Check it:

   ```bash
   hermes fetchai-bridge doctor
   hermes fetchai-bridge demo local        # expect: echo result: hello
   hermes fetchai-bridge probe-hermes      # expect: hermes_tools_server: importable
   ```

## Use

`hermes fetchai-bridge <args>` passes its arguments unchanged to `hermes-fetch-ai`:

```bash
hermes fetchai-bridge doctor --config /absolute/path/to/bridge.yaml
hermes fetchai-bridge serve --config /absolute/path/to/bridge.yaml
```

To serve real Hermes tools, put `UAGENT_SEED` (at least 32 random characters) in `$HERMES_HOME/.env` or the `uagent_seed` setting, and start from the [example config](https://github.com/ptanner66-prog/Hermes-Fetch-AI/blob/main/examples/hermes-stdio.yaml) with `hermes_mcp.command` left unset: the plugin tells the bridge which Python runs this Hermes, and `serve` starts Hermes' tools MCP server with it. The agent can load the bundled skill with `skill_view("fetchai-bridge:operate")`.

## Settings

Under `plugins.entries.fetchai-bridge.settings` (also shown in the Desktop app's plugin settings):

| Key | Purpose |
|-----|---------|
| `command` | Path to `hermes-fetch-ai` if it is not on PATH |
| `uagent_seed` | Secret, stored as `UAGENT_SEED` in Hermes' `.env`: the bridge's stable identity for `serve` (at least 32 random characters) |

## What this plugin does

- **Processes.** It runs one subprocess, without a shell, and only when you run `hermes fetchai-bridge ...`: the `hermes-fetch-ai` executable. `probe-hermes` also runs Hermes' interpreter once, to check that the tools server module imports.
- **Environment.** The bridge gets an allowlisted environment: `UAGENT_SEED`, `HERMES_HOME`, `PATH`, `HOME`, locale, temp-directory, proxy and certificate settings, and the Windows essentials. Hermes' interpreter path and `PYTHONPATH` are passed as `HERMES_FETCH_AI_HERMES_PYTHON` and `HERMES_FETCH_AI_HERMES_PYTHONPATH`. Other keys Hermes loaded from its `.env`, such as model-provider API keys, are not passed.
- **Credentials.** The only credential used is `UAGENT_SEED`, the plugin's own `config_schema` secret.
- **Agent surface.** No tools, hooks, or middleware, and one read-only skill. The agent reaches the bridge only through Hermes' terminal tool, under Hermes' normal approvals, and the skill tells it not to start `serve` unless asked. Nothing prompts or waits for input, so unattended runs do not hang.
- **Listener.** `hermes fetchai-bridge serve` is long-running. It listens on the configured port on all network interfaces (`0.0.0.0`; there is no bind-address setting, so firewall the port) and starts Hermes' tools MCP server as its own child process, with a short environment allowlist, so settings such as `HERMES_YOLO_MODE` never reach it.
- **What remote agents see.** In the example config only `skills_list` is public. It returns the name, description, and category of every installed skill, including skills you or the agent wrote; remove it from `public_tools` if that is sensitive.
- **Outbound network.** With `publish_manifest: false`, as in the example config, the bridge makes no outbound calls of its own; to reply to a remote agent it may look up that agent's endpoint in the Almanac (Agentverse's API, falling back to the Fetch ledger). With `publish_manifest: true` or mailbox mode, it also registers with the Almanac and Agentverse. When selling services, it reads Fetch's testnet ledger (`https://rest-dorado.fetch.ai` by default) when a paid call arrives, and only then; `wallet --balance` and `ledger` read it when you run them.
- **Funds.** With `publish_manifest: true`, uAgents registers the bridge on the Almanac contract, which can spend registration fees from the wallet derived from `UAGENT_SEED`. With `publish_manifest: false` nothing is spent. When selling services, buyers pay test FET on Fetch's testnet into that wallet (or `payments.payout_address`); the bridge never sends funds.
- **Selling services (off by default).** With `payments.enabled` in the config, `serve` sells the services you define: for each paid request it runs the program you configured for that service, without a shell, in an empty temporary directory, with a short environment allowlist, a timeout, and an output cap. Testnet only; mainnet is locked. Details: [payments guide](https://github.com/ptanner66-prog/Hermes-Fetch-AI/blob/main/docs/payments.md).
- **Files.** `serve` writes a JSONL audit log, without arguments or outputs, to `logging.audit_path`, by default `~/.local/state/hermes-fetch-ai/audit.jsonl` (`%LOCALAPPDATA%\HermesFetchAI\audit.jsonl` on Windows). When selling services, payment records go to a SQLite database in a private folder under `payments.state_dir` (the same default directory). `demo local` and `demo paid` use temporary files.
- **Updates and telemetry.** None: no telemetry, no self-updates.

## Notes

- Hermes handles a leading `--version` itself; `hermes fetchai-bridge doctor` prints the bridge's version.
- Hermes builds that run plugins with `plugins.isolation: host` (on `main` after 0.21.5) skip plugin CLI commands; run `hermes-fetch-ai` directly there.

## License

MIT
