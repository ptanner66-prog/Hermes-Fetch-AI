---
name: operate
description: Operate the Fetch.ai uAgents bridge for Hermes tools.
version: 1.0.0
author: Porter Tanner (ptanner66-prog)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Fetch.ai, uAgents, Agentverse, MCP, Bridge]
    related_skills: [hermes-agent]
    requires_toolsets: [terminal]
---

# Fetch.ai Bridge

The `hermes-fetch-ai` bridge puts the user's agent on Fetch.ai's network: it
sells services the user chose to other agents and ASI:One users for testnet
FET, lets Hermes buy from other agents (the `buy` skill), and can let other
agents call a small, explicitly allowed set of Hermes tools. It uses only
Hermes' tools MCP server, run as a separate process, and never exposes
conversations, messaging, or approvals.

## When to Use

- The user asks to put Hermes tools on Fetch.ai, Agentverse, or uAgents.
- The user asks to check, demo, or serve the Fetch.ai bridge.
- The user asks to sell services for FET, see payments, or pause selling.
- Do not use this skill to move funds. Paying other agents goes only through
  the `fetchai_pay` tool (the `buy` skill), which asks the user every time;
  refunds are the user's to make.

## Prerequisites

1. The bridge is installed in its own environment (it cannot share Hermes').
   If a command says it was not found, tell the user to run
   `hermes fetchai-bridge install` in a terminal; it asks them first. Do not
   install it yourself, and never into Hermes' environment.
2. The user sets the agent up with `hermes fetchai-bridge setup` in a
   terminal: it makes the agent's secret key (`UAGENT_SEED`, kept in Hermes'
   `.env`) and asks what to sell and whether Hermes may buy. Do not run setup
   for them, and never generate, print, read, or store the key yourself.
3. The local demos need nothing else: no key, no account, no network.

## How to Run

Run the bridge through the plugin command with the `terminal` tool:

```
hermes fetchai-bridge doctor
```

The plugin hands the bridge Hermes' interpreter, which `probe-hermes` and
`serve` with the example config need.

## Quick Reference

| Command | Purpose |
|---|---|
| `hermes fetchai-bridge status` | Is the agent running; what it sells, earned, and spent (`--offline` skips the ledger) |
| `hermes fetchai-bridge logs --lines 40` | What the running agent printed |
| `hermes fetchai-bridge start` / `stop` / `restart` | Run the agent in the background (only when the user asks) |
| `hermes fetchai-bridge doctor` | Bridge version, config check, dependency pins |
| `hermes fetchai-bridge probe-hermes` | Can the bridge start Hermes' tools server? |
| `hermes fetchai-bridge demo local` | Two-uAgent round trip with fake tools |
| `hermes fetchai-bridge demo paid` | An offline sale with a simulated ledger |
| `hermes fetchai-bridge demo chat` | An offline chat sale, the way an ASI:One user buys |
| `hermes fetchai-bridge seller credits` | Payments received, and which need refunds |
| `hermes fetchai-bridge seller try <service> --request "..."` | Run one service once, unpaid |
| `hermes fetchai-bridge serve --config <yaml>` | Run the bridge in the foreground (long-running; only when the user asks) |

Commands use the config `setup` wrote unless given `--config`.

## Procedure

1. Run `hermes fetchai-bridge doctor`; expect `doctor: ok`.
2. Run `hermes fetchai-bridge demo local`; expect `echo result: hello`.
3. Run `hermes fetchai-bridge probe-hermes`; expect
   `hermes_tools_server: importable`.
4. To serve real Hermes tools, the user starts from the repository's
   `examples/hermes-stdio.yaml`, leaves `hermes_mcp.command` unset, and runs
   `hermes fetchai-bridge serve --config /absolute/path/to/bridge.yaml`.
5. In that config only `skills_list` is public, and it lists every installed
   skill's name and description. Every other tool stays denylisted until the
   user changes the policy on purpose.
6. Hosted Agentverse mailbox mode is manual: follow the repository's
   `docs/agentverse-mailbox.md`. It needs an Agentverse account, and
   registration on a real network can spend from the agent's `fetch1...`
   wallet.

## Pitfalls

- `start` and `serve` run the agent until it is stopped, listening on all
  network interfaces. Do not start, stop, or restart it unless the user asks;
  `status` and `logs` are always fine to run.
- If `serve` prints `hermes backend: FAIL` or `serve: FAIL`, report the
  message; the first names a command to run by hand to see the error.
- Remote callers must follow each tool's input schema and attach the bridge's
  replay-protection metadata.
- Never write the seed or a mailbox key into YAML or a commit. The bridge
  rejects secret-shaped config values and seeds shorter than 32 characters.
- A sender's signature proves who sent a message but grants nothing by
  itself; do not make side-effecting tools public for unknown senders.
- Selling services is off unless the user's config sets `payments.enabled`,
  and runs on Fetch's testnet only. Run `seller pause`, `resume`, `ban`, or
  `unban` only when the user asks. The repository's `docs/payments.md` is the
  guide.
- A service with `runner: {type: hermes}` runs a separate guest Hermes per
  request, with only web search or no tools. Never put a key in the bridge
  config for it, and never copy the user's own Hermes `.env` to it: the guest
  reads its own keys file, which `doctor` names; the user adds the key. The
  repository's `docs/guest-hermes.md` is the guide.
- `agentverse register` lists the agent publicly on Agentverse, and the
  listing stays. Run it only when the user asks, and only with `--yes` after
  they confirm; it needs the user's Agentverse API key in the plugin setting.
  The repository's `docs/asi-one.md` is the guide.

## Verification

Through `terminal`:

```
hermes fetchai-bridge demo local
```

Success is exit code 0 with `echo result: hello` in the output.
