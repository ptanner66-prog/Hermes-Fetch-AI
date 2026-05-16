# V1 Scope

> Hardened note (2026-05-16): For final v1 decisions, see `research/HARDENED_ARCHITECTURE_DECISION.md`, `research/HARDENED_BUILD_PROMPT.md`, and `research/HARDENING_AUDIT.md`. Where this file disagrees with the hardened deliverables, the hardened deliverables are authoritative.

Date accessed: 2026-05-16

## V1 includes

- Standalone Python package `hermes-fetch-ai`.
- Existing rails first: `uagents`, `uagents-adapter`, official MCP Python SDK.
- Local direct uAgent-to-uAgent demo using `ListTools` and `CallTool`.
- Hermes MCP client shim for stdio first.
- Fallback spike path using Hermes in-process `hermes_tools_mcp_server._build_server()` if `hermes mcp serve` is blocked.
- Stable seed/address handling through environment variables.
- Configurable direct endpoint and mailbox modes.
- Optional ASI:One chat demo only after direct protocol works.
- Tool allowlist and sender allowlist.
- Redacted structured audit logs.
- Per-call timeouts, max payload, max output.
- Tests for fake MCP, policy, shim, and local direct uAgent flow.
- Docs: setup, demo, architecture, security, troubleshooting, upstream plan.

## V1 excludes

- Payments.
- Billing.
- Marketplace pricing.
- Wallet UX beyond minimum seed/address identity requirements.
- Per-skill commercial manifests.
- Broad public exposure of Hermes tools.
- Side-effecting tool demos unless explicitly operator-approved and sender-allowlisted.
- Complex multi-agent orchestration beyond request/response.
- Custom replacement for Fetch/uAgents discovery or messaging rails.
- Domain-specific examples or private workflows.
- Any OpenClaw architecture, references, examples, README language, PR framing, implementation plans, or source material.

## MVP success definition

A coding agent can run:

```bash
python -m pytest -q
python -m hermes_fetch_ai.cli demo local
```

and observe:

- local bridge uAgent starts;
- local client uAgent lists one fake or safe Hermes-backed tool;
- local client calls that tool;
- bridge returns a response;
- policy denies an unauthorized tool;
- audit log contains redacted structured events;
- no hosted dependencies are required.

## Production-grade demo success definition

With real secrets supplied through environment variables:

```bash
python -m hermes_fetch_ai.cli serve --config examples/agentverse-mailbox.yaml
```

and observe:

- stable uAgent address;
- Agentverse/Inspector mailbox link succeeds;
- protocol manifest is visible;
- direct or chat request reaches the bridge;
- a safe Hermes-backed tool returns a bounded response;
- unknown sender/tool behavior matches docs;
- no secrets appear in logs.

## Non-goals rationale

The value-add is not a new agent marketplace or execution framework. Fetch already provides public agent identity/discovery/transport. Hermes already provides local agent intelligence/tools/execution boundaries. V1 should prove the thin, reliable bridge and safety defaults.
