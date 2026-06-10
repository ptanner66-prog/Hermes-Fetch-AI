---
name: fetchai-bridge
description: Expose allowlisted Hermes tools to Fetch.ai uAgents.
version: 1.0.0
author: Porter Tanner (ptanner66-prog)
license: MIT
prerequisites:
  commands: [hermes-fetch-ai]
required_environment_variables:
  - name: UAGENT_SEED
    prompt: Stable uAgent seed for hosted mode
    help: Any long random string; it derives the agent address and wallet. Keep it out of YAML, docs, and commits.
    required_for: hosted Agentverse mailbox mode only
metadata:
  hermes:
    tags: [Fetch.ai, uAgents, Agentverse, MCP, Bridge]
    requires_toolsets: [terminal]
---

# Fetch.ai Bridge Skill

Run the hermes-fetch-ai plugin so remote Fetch.ai uAgents can list and call a
default-deny, allowlisted subset of Hermes tools over the published MCP
protocol. The bridge never exposes conversations, messaging, or permission
approvals; only the Hermes tools MCP server surface, in a separate process.

## When to Use

- The user asks to put Hermes tools on Fetch.ai rails, Agentverse, or uAgents.
- The user asks to check, demo, or serve the Fetch.ai bridge.
- Do not use this skill to move funds; it only operates the tool bridge.

## Prerequisites

1. Install the plugin in the same environment as Hermes:
   `pip install git+https://github.com/ptanner66-prog/Hermes-Fetch-AI.git`
   (PyPI name `hermes-fetch-ai` once published).
2. Local demo needs nothing else: no seed, no account, no network services.
3. Hosted mailbox mode needs `UAGENT_SEED` in `~/.hermes/.env` and an
   Agentverse account; first registration on a real network needs the agent's
   `fetch1...` wallet funded with a small amount of FET (uAgents pays the
   Almanac registration from that wallet automatically).

## How to Run

Run every command through the `terminal` tool:

```
hermes fetchai demo local
```

## Quick Reference

| Command | Purpose |
|---|---|
| `hermes fetchai doctor` | Validate bridge config and version pins |
| `hermes fetchai probe` | Report Hermes MCP seams the bridge can use |
| `hermes fetchai demo local` | Two-uAgent round trip with fake tools |
| `hermes fetchai serve --config <yaml>` | Run the bridge uAgent |

## Procedure

1. Through `terminal`, run `hermes fetchai doctor`; expect `doctor: ok`.
2. Run `hermes fetchai demo local`; expect a bridge address, visible tool
   count 1, `echo result: hello`, and an audit event count.
3. For real Hermes tools, serve the stdio config from the plugin repo
   (`examples/hermes-stdio.yaml`), with `hermes_mcp.command` set to the
   Python interpreter of the Hermes environment:
   `hermes fetchai serve --config examples/hermes-stdio.yaml`.
4. Only `skills_list` is public by default; every other exposed tool is
   denylisted until the operator edits the policy on purpose.
5. For hosted mode, set `UAGENT_SEED` in `~/.hermes/.env`, then
   `hermes fetchai serve --config examples/agentverse-mailbox.yaml` and link
   the mailbox in Agentverse.

## Pitfalls

- The Hermes tools MCP server wraps tool arguments in one required `kwargs`
  object, so remote callers must follow the served inputSchema and send
  `args={"kwargs": {...}}`.
- Never write the seed into YAML or commit it; the bridge rejects
  secret-shaped config values and fails closed when the seed is missing.
- Hosted registration on a live network fails until the agent's `fetch1...`
  wallet holds enough FET for the Almanac fee; the wallet address is derived
  from `UAGENT_SEED`.
- A sender address is routing identity, not authorization; do not widen
  `public_tools` to side-effecting tools for unknown senders.

## Verification

Through `terminal`:

```
hermes fetchai demo local
```

Success is exit code 0 with `echo result: hello` in the output.
