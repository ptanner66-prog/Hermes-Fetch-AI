# Upstream Contribution Plan: NousResearch/hermes-agent

Hermes Fetch AI should remain a standalone plugin package unless Hermes maintainers explicitly request a larger footprint. This document is a maintainer-facing plan, not a claim that Hermes core already enables every plugin command out of the box.

## Recommended upstream shape

Use the smallest acceptable surface:

1. standalone package with `hermes_agent.plugins` entry point;
2. optional Hermes docs/catalog mention;
3. optional skill that teaches Hermes users to run `hermes-fetch-ai`;
4. only if maintainers request it, setup UX that installs and enables the package.

Do **not** propose vendoring bridge code into Hermes core.

## Current verified surface in this repo

- Package CLI: `hermes-fetch-ai doctor|probe-hermes|serve|demo`.
- Plugin entry point: `fetchai = "hermes_fetch_ai.hermes_plugin"`.
- If a target Hermes build enables entry-point plugins and wires plugin CLI commands, the plugin exposes `hermes fetchai doctor|probe|serve|demo`.
- The Hermes-backed stdio backend depends on `agent.transports.hermes_tools_mcp_server`; this is version-dependent and should be treated as gated until Hermes maintainers bless it as stable.

## Discussion first

Open a Discussion/issue before a Hermes PR.

Draft title:

```text
Integration: Fetch.ai uAgents bridge as a standalone Hermes plugin
```

Draft body:

```text
hermes-fetch-ai is a standalone plugin package that exposes a default-deny,
policy-gated subset of Hermes tools to Fetch.ai uAgents. Hermes stays the local
execution layer; Fetch/uAgents supplies identity, signed envelopes, addressing,
and discovery rails.

Current package surface:
- console script: hermes-fetch-ai doctor|probe-hermes|serve|demo
- plugin entry point: hermes_agent.plugins / fetchai
- no Hermes core files patched
- no network surface enabled by default

Questions for maintainers:
1. Do you prefer this remain an external plugin with a docs/catalog listing?
2. Would an optional skill that invokes hermes-fetch-ai be welcome?
3. Is there a supported path for setup to install and enable third-party entry-point plugins?
4. Is agent.transports.hermes_tools_mcp_server a stable public tools-server seam?
```

## Candidate PR A: optional skill

Only after maintainer signal, propose a small skill under the Hermes-approved skill location.

Title:

```text
feat(skills): add fetchai-bridge optional skill
```

Payload in this repository:

```text
upstream/hermes-pr/SUBMIT.md
upstream/hermes-pr/optional-skills/autonomous-ai-agents/fetchai-bridge/SKILL.md
upstream/hermes-pr/tests/skills/test_fetchai_bridge_skill.py
```

The skill should use `hermes-fetch-ai` as the verified command. If Hermes core later guarantees plugin enablement/CLI wiring, the skill can mention `hermes fetchai ...` as an enabled-plugin alias.

## Candidate PR B: docs/catalog page

Title:

```text
docs(website): add Fetch.ai uAgents bridge integration guide
```

One page should explain:

- the package is standalone;
- install/run commands use `hermes-fetch-ai` unless plugin enablement is confirmed;
- security defaults are default-deny, replay-protected, rate-limited, and audited;
- the conversations/messaging MCP surface is excluded;
- the Hermes tools-server backend is version-dependent until maintainers mark it stable.

## What not to propose

- in-tree bridge adapter directory;
- changes to core agent runtime;
- new default model tools/toolsets;
- new `HERMES_*` env vars;
- bridging `hermes mcp serve` conversations/messaging;
- public claims that pip install alone guarantees `hermes fetchai ...` on all Hermes versions.
