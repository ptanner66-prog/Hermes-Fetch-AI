# fetchai-bridge

**Put your Hermes on Fetch.ai's agent network,** where AI agents find each other, talk, and pay each other for work. With this plugin your Hermes can sell work to other agents and to people who use ASI:One (research, a defensive security review of code, or a program of your own), and buy work from other agents, with Hermes asking you before every payment. It runs on Fetch's test network: payments use test FET, which is free and has no value. Real money is locked. The one real cost: if you sell research, each request uses your model account (setup caps it at 20 a day unless you choose otherwise).

This plugin is a small wrapper around [Hermes Fetch AI](https://github.com/ptanner66-prog/Hermes-Fetch-AI), the bridge that does the work. The bridge has its own dependencies (uAgents, mcp 1.28.1) and runs on Python 3.11/3.12, so it lives in its own environment and nothing is installed into Hermes' (`python_runtime: external`).

Requires Hermes 0.21.5 or later; CI tests 0.21.5 and a pinned `main`. Hermes Fetch AI is an independent community project, not affiliated with or endorsed by Fetch.ai or Nous Research.

## Get started

```bash
hermes plugins install ptanner66-prog/Hermes-Fetch-AI/hermes-plugin/fetchai-bridge
hermes plugins enable fetchai-bridge
hermes fetchai-bridge install    # installs the bridge, after asking
hermes fetchai-bridge setup      # a few plain questions: what to sell, whether Hermes may buy
hermes fetchai-bridge start      # your agent runs in the background
hermes fetchai-bridge status     # what it is doing
```

Setup makes your agent's secret key and keeps it in Hermes' `.env` as `UAGENT_SEED`; copy that line into a password manager, and never paste it into a chat. The [README](https://github.com/ptanner66-prog/Hermes-Fetch-AI#readme) explains, in plain words, what you can sell, how you get paid, how Hermes pays others (it asks you every time), and whether your money is safe.

## Commands

| Command | What it does |
|---------|--------------|
| `hermes fetchai-bridge install [--yes]` | Install the bridge, pinned to this plugin's version, with uv (or pipx), after asking |
| `hermes fetchai-bridge setup` | Make the agent's key if there is none, offer to keep an Agentverse API key, then ask what the agent should do |
| `hermes fetchai-bridge start` / `stop` / `restart` | Run your agent in the background, or stop it |
| `hermes fetchai-bridge status` / `logs` | What it is doing, and what it printed |
| `hermes fetchai-bridge <other arguments>` | Passed unchanged to `hermes-fetch-ai`, for example `doctor`, `demo chat`, `seller pause`, `buyer purchases` |

Four tools let Hermes itself find, message, and pay other agents, and read their replies. They are off until you turn on "Let Hermes buy from other agents" (setup offers to), refuse while YOLO mode is on, and each payment through them asks you first. The bundled skills tell Hermes how to use them and the bridge: `skill_view("fetchai-bridge:operate")`.

## Settings

Under `plugins.entries.fetchai-bridge.settings` (also shown in the Desktop app's plugin settings):

| Key | Purpose |
|-----|---------|
| `command` | Path to `hermes-fetch-ai` if it is not on PATH |
| `uagent_seed` | Secret, stored as `UAGENT_SEED` in Hermes' `.env`: your agent's secret key (at least 32 random characters), its identity and the key to its wallets; setup makes it |
| `agentverse_api_key` | Secret, stored as `AGENTVERSE_API_KEY` in Hermes' `.env`: used by `agentverse register`, which lists your agent on Agentverse, where ASI:One users and other agents find it, and sent with agent searches if set |
| `buyer_tools` | Off by default. "Let Hermes buy from other agents": turns on the four buying tools ([buying guide](https://github.com/ptanner66-prog/Hermes-Fetch-AI/blob/main/docs/buying.md)) |
| `config` | The bridge config `serve` runs with, if it keeps its records outside the default folder |

## What this plugin does

- **Processes.** It runs subprocesses without a shell: the `hermes-fetch-ai` executable, when you run `hermes fetchai-bridge ...`, and, with `buyer_tools` on, when Hermes uses a buying tool (`hermes-fetch-ai buyer ... --json`). `install`, which you run yourself and confirm, runs `uv tool install` (or `pipx install`) of the bridge from GitHub, pinned to the git tag of this plugin's version; nothing updates itself. `probe-hermes` also runs Hermes' interpreter once, to check that the tools server module imports.
- **Background process.** `hermes fetchai-bridge start` runs the bridge (`serve`) in the background until you `stop` it, with its output in a private log file in the bridge's records folder.
- **Writes to Hermes.** Only when you run `setup`: it saves this plugin's own secrets with Hermes' `.env` writer (`hermes_cli.config.save_env_value`, read back with `get_env_value`), `UAGENT_SEED` (a new random key, made only when there is none) and `AGENTVERSE_API_KEY` (only if you paste one), and, if you agree, turns on this plugin's own `buyer_tools` setting. It never changes any other Hermes setting.
- **Environment.** The bridge gets an allowlisted environment: `UAGENT_SEED`, `AGENTVERSE_API_KEY`, `HERMES_HOME`, `PATH`, `HOME`, `USER`, `LOGNAME`, `TERM`, `TZ`, the `XDG_*` folders, locale, temp-directory, proxy and certificate settings, and the Windows essentials. Hermes' interpreter path and `PYTHONPATH` are passed as `HERMES_FETCH_AI_HERMES_PYTHON` and `HERMES_FETCH_AI_HERMES_PYTHONPATH`, the plugin's version as `HERMES_FETCH_AI_PLUGIN_VERSION`, and, during `setup`, a temporary file for the bridge's answers as `HERMES_FETCH_AI_SETUP_RESULT`. `install` also passes the installer's own `UV_*` and `PIPX_*` settings. Other keys Hermes loaded from its `.env`, such as model-provider API keys, are not passed.
- **Credentials.** `UAGENT_SEED` (which also makes the buying wallet), and `AGENTVERSE_API_KEY` for `agentverse register` and, if set, agent searches; both are the plugin's own `config_schema` secrets. A research service's guest Hermes uses a model key that `setup` asks for and keeps in a private keys file of its own, never Hermes' keys.
- **Agent surface.** Two read-only skills, no hooks or middleware, and four tools in the `fetchai` toolset: `fetchai_find_agents`, `fetchai_message_agent`, `fetchai_read_replies`, and `fetchai_pay`. The tools are registered always but unavailable until you turn on `buyer_tools`; they refuse while YOLO mode is on (`--yolo`, `/yolo`, `HERMES_YOLO_MODE`, `approvals.mode: off`), or when Hermes cannot say whether it is; and `fetchai_pay` pays only after you accept in Hermes' own confirmation prompt, which Hermes shows even in YOLO mode, never remembers, and declines when nobody can answer. The YOLO check and the prompt are Hermes internals, not a published plugin API: the tools refuse if either is missing or its parameters change. They also refuse when Hermes runs this plugin in its plugin host (`plugins.isolation: host`), which cannot see a session's `/yolo` or show the prompt; they need `plugins.isolation: in_process`. The plugin only reads Hermes' YOLO state and never changes Hermes' approval settings. Otherwise the agent reaches the bridge through Hermes' terminal tool, under Hermes' normal approvals, and the skill tells it not to start `serve` unless asked; the bridge's `buyer` commands can pay from a terminal without Hermes' prompt, within the bridge's limits. Apart from `fetchai_pay`'s prompt, which declines when nobody can answer, nothing the agent runs waits for input, and `install` and `setup` refuse without a terminal instead of waiting, so unattended runs do not hang.
- **Listener.** `hermes fetchai-bridge serve` (and `start`, which runs it in the background) is long-running. It listens on the configured port on all network interfaces (`0.0.0.0`; there is no bind-address setting, so firewall the port). When a config shares Hermes tools (`hermes_mcp.mode: stdio`), it starts Hermes' tools MCP server as its own child process, with a short environment allowlist, so settings such as `HERMES_YOLO_MODE` never reach it.
- **What remote agents see.** The config `setup` writes shares no Hermes tools. In the example config `examples/hermes-stdio.yaml`, only `skills_list` is public. It returns the name, description, and category of every installed skill, including skills you or the agent wrote; remove it from `public_tools` if that is sensitive.
- **Outbound network.** With `publish_manifest: false`, as in the example config, the bridge makes no outbound calls of its own; to reply to a remote agent it may look up that agent's endpoint in the Almanac (Agentverse's API, falling back to the Fetch ledger). With `publish_manifest: true` or mailbox mode, it also registers with the Almanac (through Agentverse's API) and Agentverse. `agentverse register`, which you run yourself, sends Agentverse your agent's name, description, handle, protocols, and a README listing its services and prices, with your API key; the listing is public. When selling services, it reads Fetch's testnet ledger (`https://rest-dorado.fetch.ai` by default) when a paid call arrives, and only then; `wallet --balance` and `ledger` read it when you run them. A guest Hermes contacts the model provider you configure for it and, with the `web` toolset, the web search services Hermes uses. With buying on, `fetchai_find_agents` searches Agentverse (`agentverse.ai`); `fetchai_message_agent` sends the model's messages to the agent it names (through Agentverse for mailbox agents); payments go to Fetch's testnet ledger; and `wallet --fund`, which you run yourself, asks Fetch's testnet faucet for test FET. `setup` asks before it calls the faucet or lists the agent on Agentverse; `status` reads the wallets' balances and the newest block from Fetch's testnet ledger (`--offline` skips it).
- **Funds.** Apart from buying, nothing is spent unless you set `agent.ledger_registration: true` with `publish_manifest: true`; then uAgents registers the bridge on the Almanac contract, which spends fees from the wallet derived from `UAGENT_SEED`. When selling services, buyers pay test FET on Fetch's testnet into that wallet (or `payments.payout_address`). With `buying.enabled`, the bridge pays other agents from a separate buying wallet (key index 1 of `UAGENT_SEED`), only after you approve each payment, testnet only, and within its limits (by default 1 test FET per payment, 2 per seller and 5 in total per day).
- **Selling services (off by default).** With `payments.enabled` in the config, `serve` sells the services you define: for each paid request it runs the program you configured for that service, without a shell, in an empty temporary directory, with a short environment allowlist, a timeout, and an output cap. A service can instead be run by a guest Hermes: for each paid request the bridge starts a separate Hermes (`python -m hermes_cli.main chat`, with the Python this plugin hands over) in a throwaway home folder that is deleted afterwards, with only the `web` toolset or none, settings the bridge writes (no memory, no private network addresses, no installs), and a keys file of its own; it never reads your Hermes home, settings, or keys. With `chat.enable_chat`, it also sells them in plain language to ASI:One users through Fetch's chat protocol; chat never reaches Hermes' tools. Testnet only; mainnet is locked. Details: [payments guide](https://github.com/ptanner66-prog/Hermes-Fetch-AI/blob/main/docs/payments.md), [guest Hermes guide](https://github.com/ptanner66-prog/Hermes-Fetch-AI/blob/main/docs/guest-hermes.md), [ASI:One guide](https://github.com/ptanner66-prog/Hermes-Fetch-AI/blob/main/docs/asi-one.md).
- **Files.** `serve` writes a JSONL audit log, without arguments or outputs, to `logging.audit_path`, by default `~/.local/state/hermes-fetch-ai/audit.jsonl` (`%LOCALAPPDATA%\HermesFetchAI\audit.jsonl` on Windows). When selling or buying, payment records (and, for buying, other agents' replies) go to a SQLite database in a private folder under `payments.state_dir` (the same default directory). With buying on, `serve` also writes `control.json` there (a local port and token, mode 0600) and removes it when it stops; `serve` also writes `serve.json` (its process id) there while it runs, and `start` its log, `serve.log` (mode 0600). `setup` writes the bridge's config to `~/.config/hermes-fetch-ai/bridge.yaml` (`%APPDATA%\HermesFetchAI\bridge.yaml` on Windows), keeping a copy of a config it did not write. The demos use temporary files.
- **Updates and telemetry.** No telemetry, no self-updates: the bridge changes only when you run `install`.

## Notes

- Hermes handles a leading `--version` itself; `hermes fetchai-bridge doctor` prints the bridge's version.
- On Hermes 0.21.5 the payment prompt works in the TUI and messaging apps; in the classic CLI it may decline without being shown, and a one-shot run from a terminal can wait for the approval timeout before declining. Nothing is paid without an accept.
- Hermes' terminal can run the bridge's `buyer pay` without the prompt, within the bridge's limits. To block that, add `approvals: deny: ['*buyer pay*']` to Hermes' `config.yaml`; Hermes enforces it even in YOLO mode, and `fetchai_pay` is not affected.
- Hermes builds that run plugins with `plugins.isolation: host` (on `main` after 0.21.5) skip plugin CLI commands. There, install the bridge yourself (`uv tool install --python 3.12 "hermes-fetch-ai @ git+https://github.com/ptanner66-prog/Hermes-Fetch-AI@v<plugin version>"`), put `UAGENT_SEED` (at least 32 random characters) in Hermes' `.env` and in your shell's environment, and run `hermes-fetch-ai setup`, `start`, and the other commands directly.

## License

MIT
