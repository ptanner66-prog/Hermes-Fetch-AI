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

The `hermes-fetch-ai` bridge lets remote Fetch.ai uAgents list and call a
default-deny, allowlisted subset of Hermes tools over the published MCP
protocol. It never exposes conversations, messaging, or permission approvals;
only the Hermes tools MCP server, run as a separate process.

## When to Use

- The user asks to put Hermes tools on Fetch.ai rails, Agentverse, or uAgents.
- The user asks to check, demo, or serve the Fetch.ai bridge.
- Do not use this skill to move funds; it only operates the tool bridge.

## Prerequisites

1. The bridge is installed in its own environment (it cannot share Hermes'):
   `uv tool install --python 3.12 "hermes-fetch-ai @ git+https://github.com/ptanner66-prog/Hermes-Fetch-AI"`.
   If `hermes-fetch-ai` is not on PATH, tell the user to install it; do not
   install it into Hermes' environment.
2. The local demo needs nothing else: no seed, no account, no network services.
3. Serving real Hermes tools needs `UAGENT_SEED` (at least 32 random
   characters) in the environment, set by the user. Never generate, print, or
   store it yourself.

## How to Run

Run the bridge directly through the `terminal` tool:

```
hermes-fetch-ai doctor
```

The user can run the same commands as `hermes fetchai-bridge <args>`.

## Quick Reference

| Command | Purpose |
|---|---|
| `hermes-fetch-ai doctor` | Validate bridge config and version pins |
| `hermes-fetch-ai probe-hermes` | Report Hermes MCP seams the bridge can use |
| `hermes-fetch-ai demo local` | Two-uAgent round trip with fake tools |
| `hermes-fetch-ai serve --config <yaml>` | Run the bridge uAgent (long-running) |

## Procedure

1. Run `hermes-fetch-ai doctor`; expect `doctor: ok`.
2. Run `hermes-fetch-ai demo local`; expect `echo result: hello`.
3. To serve real Hermes tools, the user copies the repository's
   `examples/hermes-stdio.yaml` and runs
   `hermes fetchai-bridge serve --config /absolute/path/to/bridge.yaml`.
   The plugin passes Hermes' own Python to the bridge, so
   `hermes_mcp.command` stays unset. Running `hermes-fetch-ai serve`
   directly instead needs `hermes_mcp.command` set to the Python interpreter
   of the Hermes environment.
4. Only `skills_list` is public by default; every other Hermes tool is
   denylisted until the operator edits the policy on purpose.
5. Hosted Agentverse mailbox mode is manual: follow the repository's
   `docs/agentverse-mailbox.md`. It needs an Agentverse account, and first
   registration on a real network may need the agent's `fetch1...` wallet
   funded.

## Pitfalls

- `serve` runs until stopped. Do not start it from an agent session unless the
  user asks; production deployments run it under a supervisor such as systemd.
- If `serve` prints `hermes backend: FAIL`, run the command that message
  names to see the error.
- Remote callers must follow each tool's served input schema and attach the
  bridge's replay metadata.
- Never write the seed or a mailbox key into YAML or a commit. The bridge
  rejects secret-shaped config values and seeds shorter than 32 characters.
- A sender address is routing identity, not authorization; do not widen
  `public_tools` to side-effecting tools for unknown senders.

## Verification

Through `terminal`:

```
hermes-fetch-ai demo local
```

Success is exit code 0 with `echo result: hello` in the output.
