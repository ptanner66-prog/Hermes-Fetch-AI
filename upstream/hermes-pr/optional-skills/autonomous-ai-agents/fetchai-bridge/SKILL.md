---
name: fetchai-bridge
description: Expose allowlisted Hermes tools to Fetch.ai uAgents.
version: 1.0.0
author: Porter Tanner (ptanner66-prog)
license: MIT
platforms: [linux, macos, windows]
prerequisites:
  commands: [hermes-fetch-ai]
required_environment_variables:
  - name: UAGENT_SEED
    prompt: Stable uAgent seed for served bridges
    help: At least 32 random characters; it derives the agent address and wallet. Keep it out of YAML, docs, and commits.
    required_for: serving real Hermes tools or hosted Agentverse mailbox mode
metadata:
  hermes:
    tags: [Fetch.ai, uAgents, Agentverse, MCP, Bridge]
    related_skills: [hermes-agent]
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

1. Install the bridge as its own tool, not into the Hermes environment (its
   pinned dependencies differ from Hermes'):
   `uv tool install --python 3.12 "hermes-fetch-ai @ git+https://github.com/ptanner66-prog/Hermes-Fetch-AI@<full-commit-sha>"`
   (`uv tool install hermes-fetch-ai` once it is on PyPI).
2. The local demo needs nothing else: no seed, no account, no network services.
3. Serving real Hermes tools or hosted mailbox mode needs `UAGENT_SEED` in the
   process environment; mailbox mode also needs an Agentverse account, and first
   registration on a real network may need the agent's `fetch1...` wallet funded.

## How to Run

Run every command through the `terminal` tool:

```
hermes-fetch-ai demo local
```

Prefer the `hermes-fetch-ai` command. The package also ships a `fetchai` Hermes
plugin entry point, but Hermes only loads it from its own environment and only
after `hermes plugins enable fetchai`.

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
3. For real Hermes tools, set `UAGENT_SEED`, then serve a stdio config from the
   plugin repo with `hermes_mcp.command` set to the Hermes environment's Python:
   `hermes-fetch-ai serve --config /absolute/path/to/examples/hermes-stdio.yaml`.
   If it prints `hermes backend: FAIL`, run that Python with
   `-m agent.transports.hermes_tools_mcp_server` to see why.
4. Only `skills_list` is public by default; every other exposed tool is
   denylisted until the operator edits the policy on purpose.
5. For hosted mode, follow the plugin repo's `docs/agentverse-mailbox.md`.

## Pitfalls

- Remote callers must follow the served inputSchema. Current Hermes serves flat
  arguments (for example `{"query": "..."}` for `web_search`); hermes-agent
  v0.16.x wrapped them in one `kwargs` object.
- Never write the seed or mailbox key into YAML or commit it; the bridge rejects
  secret-shaped config values, short seeds, and fails closed when the seed is
  missing.
- Hosted registration on a live network can fail until the agent's `fetch1...`
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
