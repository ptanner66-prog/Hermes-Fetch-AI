# Agentverse Mailbox Setup (Manual, Unverified)

> **Status:** this tier has not been exercised end to end by this project's CI or
> maintainers. The steps below follow the uAgents 0.25.x mailbox flow as implemented
> in the pinned `uagents` package. Treat the first run as an experiment on
> `network: testnet`, and report what you see.

The local demo and the HTTP serve smoke test need none of this. Mailbox mode is for
reaching the bridge from remote uAgents through Agentverse without exposing a public
endpoint.

## What you need

1. An Agentverse account (agentverse.ai).
2. A dedicated agent seed in the environment as `UAGENT_SEED`, at least 32 characters.
   Never put it in YAML, docs, shell history, commits, or screenshots.
   Generate one with:

   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

3. Testnet funds for the derived `fetch1...` address only if the current Agentverse or
   Almanac registration flow asks for them. Local CI never depends on funding.

## Steps

1. Start from `examples/agentverse-mailbox.yaml` (`mode: mailbox`,
   `publish_manifest: true`, `enable_agent_inspector: true`). Copy it, then point
   `hermes_mcp` at your Hermes backend (see `examples/hermes-stdio.yaml`) and keep
   `policy.public_tools` empty or minimal.
2. Check the config:

   ```bash
   export UAGENT_SEED="<your seed>"        # PowerShell: $env:UAGENT_SEED = "<your seed>"
   hermes-fetch-ai doctor --config /absolute/path/to/mailbox.yaml
   ```

3. Start the bridge:

   ```bash
   hermes-fetch-ai serve --config /absolute/path/to/mailbox.yaml
   ```

   uAgents logs a line like
   `Agent inspector available at https://agentverse.ai/inspect/?uri=http%3A//127.0.0.1%3A8003&address=agent1q...`.
   Until the mailbox exists it also logs
   `Agent mailbox not found: create one using the agent inspector`.
4. Open the inspector URL **in a browser on the same machine** (it talks to
   `http://127.0.0.1:<port>`), sign in to Agentverse, and choose **Connect → Mailbox**.
   The page calls the bridge's local `/connect` endpoint with your Agentverse token;
   the bridge proves its identity to Agentverse and registers its mailbox.
5. Confirm the "mailbox not found" warning stops and the agent appears in your
   Agentverse agent list.
6. Send `ListTools` from a remote test uAgent to the bridge address and check the audit
   log for an `allowed` `list_tools` event.

## Security notes

- **The inspector's `/connect` and `/disconnect` endpoints are unauthenticated.** They
  accept any Agentverse user token, and the uAgents server binds `0.0.0.0`. While
  `enable_agent_inspector: true`, anyone who can reach the port could attach the bridge
  to their own Agentverse account or disconnect it. Firewall the port to localhost
  during setup.
- After the mailbox is connected, set `enable_agent_inspector: false` and restart. In
  mailbox mode with the inspector off, the bridge opens no local HTTP listener at all
  and receives messages only through the mailbox. (Expected from the uAgents code path;
  verify it in your setup.)
- `CallTool` still requires replay metadata, and every policy, rate-limit, and
  validation rule applies exactly as in endpoint mode.
- Never share the seed, recovery phrases, private keys, Agentverse tokens, or funding
  transaction details in issues, PRs, or logs.

`hermes-fetch-ai demo mailbox` only checks that the mailbox example config loads with
your `UAGENT_SEED` and points here; it does not contact Agentverse.
