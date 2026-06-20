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

Run the `hermes-fetch-ai` package so remote Fetch.ai uAgents can list and call a
default-deny, allowlisted subset of Hermes tools over the published MCP
protocol. The bridge never exposes conversations, messaging, or permission
approvals; only the Hermes tools MCP server surface, in a separate process.

## When to Use

- The user asks to put Hermes tools on Fetch.ai rails, Agentverse, or uAgents.
- The user asks to check, demo, or serve the Fetch.ai bridge.
- Do not use this skill to move funds; it only operates the tool bridge.

## Prerequisites

1. Install the package in the same environment as Hermes:
   `pip install git+https://github.com/ptanner66-prog/Hermes-Fetch-AI.git`
   (PyPI name `hermes-fetch-ai` once published).
2. Local demo needs nothing else: no seed, no account, no network services.
3. Hosted mailbox mode needs `UAGENT_SEED` in the process environment and an
   Agentverse account; first registration on a real network needs the agent's
   `fetch1...` wallet funded with a small amount of FET.

## How to Run

Run every command through the `terminal` tool:

```
hermes-fetch-ai demo local
```

If a future Hermes release installs, enables, and wires the plugin CLI, the
alias is `hermes fetchai ...`. Prefer `hermes-fetch-ai` unless that integration
has been verified in the active Hermes installation.

## Quick Reference

| Command | Purpose |
|---|---|
| `hermes-fetch-ai doctor` | Validate bridge config and version pins |
| `hermes-fetch-ai probe-hermes` | Report Hermes MCP seams the bridge can use |
| `hermes-fetch-ai demo local` | Two-uAgent round trip with fake tools |
| `hermes-fetch-ai serve --config <yaml>` | Run the bridge uAgent |

## Procedure

1. Through `terminal`, run `hermes-fetch-ai doctor`; expect `doctor: ok`.
2. Run `hermes-fetch-ai demo local`; expect a bridge address, visible tool
   count 1, `echo result: hello`, and an audit event count.
3. For real Hermes tools, serve a stdio config from the plugin repo with
   `hermes_mcp.command` set to the Python interpreter of the Hermes environment:
   `hermes-fetch-ai serve --config /absolute/path/to/examples/hermes-stdio.yaml`.
4. Only `skills_list` is public by default; every other exposed tool is
   denylisted until the operator edits the policy on purpose.
5. For hosted mode, set `UAGENT_SEED` outside YAML, then run
   `hermes-fetch-ai serve --config /absolute/path/to/examples/agentverse-mailbox.yaml`
   and link the mailbox in Agentverse.

## Pitfalls

- The Hermes tools MCP server wraps tool arguments in one required `kwargs`
  object, so remote callers must follow the served inputSchema and send
  `args={"kwargs": {...}}`.
- Never write the seed or mailbox key into YAML or commit it; the bridge rejects
  secret-shaped config values and fails closed when the seed is missing.
- Hosted registration on a live network fails until the agent's `fetch1...`
  wallet holds enough FET for the Almanac fee; the wallet address is derived
  from `UAGENT_SEED`.
- A sender address is routing identity, not authorization; do not widen
  `public_tools` to side-effecting tools for unknown senders.

## Verification

Through `terminal`:

```
hermes-fetch-ai demo local
```

Success is exit code 0 with `echo result: hello` in the output.
