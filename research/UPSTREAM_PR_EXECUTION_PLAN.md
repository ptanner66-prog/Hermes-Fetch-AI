# Upstream PR Execution Plan

Updated: 2026-05-17T03:35:34Z

Status: do not open an upstream PR in this run. No upstream branch was created. The local Hermes checkout at `C:\Users\ptann\OneDrive\Work\hermes-agent-main` is reference-only for this pass because it is dirty and behind `origin/main` by 1.

## Current recommendation

Implement a Hermes-native optional Fetch/uAgents bridge as a plugin or small CLI surface, not a wholesale import of this standalone proof.

Preferred first PR title:

`feat(plugins): add optional Fetch uAgents bridge for Hermes MCP tools`

Core idea:

- Hermes remains the local execution agent.
- Fetch/uAgents supplies identity, addressing, mailbox/delivery, protocol messages, and discovery rails.
- The bridge is a policy and transport membrane around `hermes mcp serve`.
- The integration is default-off and optional.

## Why this shape changed/solidified in the MOE pass

The MOE pass proved a real `hermes mcp serve` stdio path locally:

- backend probe: `backend: ok: 10 tools`;
- bridge demo: `conversations_list` returned `{"count": 0, "conversations": []}` through uAgents/MCP bridge handlers;
- public policy exposed only two read/poll tools in the demo config.

That evidence means PR one does not need to import Hermes internals or create a new execution layer. The thinnest upstream shape is plugin/CLI wiring around Hermes' existing MCP server.

The Fetch sweep also confirmed that uAgents already provides MCP protocol models/spec, mailbox, Agentverse/Almanac discovery context, and payment message models. Therefore PR one should not create new identity/discovery/payment rails.

## Scope for PR one

Include:

1. Optional plugin or CLI command
   - Candidate command: `hermes uagents serve` or equivalent plugin-provided command.
   - Starts a Fetch/uAgents bridge that proxies selected MCP tool calls to local `hermes mcp serve`.
   - Default disabled.

2. Optional dependency handling
   - No eager import of `uagents`, `uagents-core`, or `uagents-adapter[mcp]` at Hermes startup.
   - Clear error if the command is used without optional packages.
   - No behavior change for users who never enable the bridge.

3. Config/profile integration
   - Use Hermes config/profile conventions and home helpers.
   - Keep secrets in environment/operator-managed channels, never in committed YAML.
   - Local examples should use environment-variable command paths when needed.

4. Policy defaults
   - Public tools default to empty or one read-only sample.
   - Side-effecting send/approval tools denied by default.
   - Sender-specific allowlists documented, not guessed.
   - Payment status must not override tool policy.

5. Tests
   - Missing optional dependency gives clear error.
   - Default config is disabled.
   - Fake local uAgents dispatcher can list/call a safe MCP tool.
   - Side-effecting Hermes tools are denied by default.
   - Stdio command construction avoids shell invocation and filters environment.
   - Secret-shaped config values are rejected.
   - Docs/config examples contain no secrets.

6. Docs
   - Short integration page: "Connect Hermes to Fetch/uAgents".
   - Explain the split: Fetch handles agent network rails; Hermes handles local tools/execution.
   - Include Agentverse mailbox operator checklist.
   - Include payment dry-run note: negotiation only, no settlement.
   - Include security defaults and denied tool examples.

## Exclude from PR one unless maintainers explicitly request

- A2A external-agent adapter work.
- Hosted Agentverse account automation.
- Wallet custody or funded settlement.
- Production deployment automation.
- Broad marketplace UX.
- Changes to Hermes prompt defaults, tool defaults, or core agent loop.
- Gateway platform adapter work.

## A2A decision

Agentverse external A2A is a legitimate follow-up candidate, not the first patch.

Reason:

- Fetch/uAgents upstream includes an A2A inbound adapter path.
- It appears to require a public endpoint and Agent Card flow.
- It is useful for broader Agentverse/ASI interoperability, but it expands review scope.

PR one should be native uAgents/MCP bridge. A later PR can add A2A Agent Card/external-agent support if maintainers want that path.

## Why not a gateway platform adapter

The bridge is RPC/tool routing over uAgent messages, not a human messaging platform. It should not be implemented as a gateway platform adapter unless maintainers specifically direct that architecture.

## Files to inspect/touch in Hermes upstream

Inspect first:

- `AGENTS.md`
- `mcp_serve.py`
- `tests/test_mcp_serve.py`
- `hermes_cli/main.py`
- `hermes_cli/config.py`
- `hermes_cli/plugins.py`
- `hermes_cli/plugins_cmd.py`
- plugin loader paths and docs
- docs for plugins, MCP, CLI commands, and config

Likely files to touch for plugin-first PR:

- canonical plugin directory or package path;
- plugin metadata/manifest file;
- plugin command module;
- tests under the current plugin/CLI test layout;
- docs page under integrations/plugins/MCP area.

Only touch core CLI files if needed to expose generic plugin command registration. If that seam is missing, make the generic plugin-command seam a separate small PR.

## PR body draft

Summary:

- Adds an optional, default-off Fetch/uAgents bridge that exposes selected Hermes MCP tools through uAgents identity, addressing, and mailbox/discovery rails.
- Hermes remains the local execution agent; Fetch/uAgents supplies network identity, delivery, protocol manifest/discovery context, and payment negotiation models.
- Includes safe defaults, policy-filtered tool exposure, redacted audit, and local tests.

Why this shape:

- Thin wrapper over existing Hermes `mcp serve` surface.
- Optional dependency; no default behavior change.
- No new agent framework.
- No settlement or hosted account automation.

Validation plan:

- Unit tests for config/default-off/missing dependency.
- Local fake uAgents dispatcher test.
- Stdio command and policy-filter tests.
- Existing Hermes MCP tests unchanged.
- Docs build/lint if available.

What stays untouched:

- Core prompt/tool defaults.
- Gateway platform adapters.
- Production settlement and wallet handling.
- Operator-owned hosted mailbox setup.

## Evidence from standalone repo to cite

- `77 passed in 17.94s`.
- Ruff/mypy/contamination green.
- Local fake demo returns `echo result: hello`.
- Hermes stdio backend probe returns `backend: ok: 10 tools`.
- Hermes stdio bridge demo returns empty `conversations_list` through the bridge.
- Payment dry-run demo returns `CompletePayment` with no settlement.
- Mailbox config fails closed without operator seed.

## Operator-owned follow-up after PR shape is confirmed

- Create/link Agentverse mailbox entry.
- Start bridge with seed only in operator shell.
- Send remote uAgent `ListTools` and `CallTool(conversations_list)`.
- Record non-secret transcript and manifest/digest evidence.
- Decide separately whether testnet payment proof is warranted.
