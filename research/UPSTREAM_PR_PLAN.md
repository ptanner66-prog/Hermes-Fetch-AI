# Upstream Hermes PR Plan

Date accessed: 2026-05-16

## Principle

The upstream PR should read as Hermes-native code, not as a pasted standalone app. The standalone repo proves the integration privately; upstream gets only the minimal, maintained slice that belongs in Hermes.

## What should be proven before upstreaming

- Local direct uAgent-to-Hermes flow works.
- Agentverse/Mailbox demo works or the blocker is documented.
- Security defaults are tested: allowlists, timeouts, payload/output caps, redaction, audit logs.
- Hermes MCP surface is verified against actual installed Hermes package/source.
- Version pins and compatibility risks are known.
- Public docs avoid overclaiming.

## Likely upstream shape

Two plausible upstream paths:

### Option A: Hermes gateway platform adapter

Add a uAgents/Fetch platform adapter under Hermes gateway/platform conventions.

Likely touched areas, based on local wheel structure:

- `gateway/platforms/uagents.py` or plugin package under `plugins/platforms/uagents/`.
- `gateway/platform_registry.py` registration via `PlatformEntry`.
- `gateway/platforms/base.py` interface conformance.
- `gateway/config.py` platform config parsing.
- docs for platform setup.
- tests for platform adapter message mapping.

This is preferred if the integration should expose Hermes as a messaging platform like Telegram/Discord/Slack style adapters.

### Option B: Hermes MCP/uAgents bridge command/plugin

Add a Hermes-native `hermes uagents serve` or plugin command that wraps Hermes MCP or gateway session into a uAgent.

Likely touched areas:

- CLI parser/command module.
- plugin manifest or platform registration.
- MCP bridge module using existing `tools/mcp_tool.py` and/or server builder concepts.
- docs and config migration.

This is preferred if maintainers want Fetch/uAgents to be an optional extension rather than a first-class messaging platform.

## Code that may port from standalone

- `HermesMCPClientShim` only if Hermes still needs a client shim around its own MCP server.
- Result normalizer.
- Policy primitives if they align with Hermes existing approval/tool policy model.
- Redacted audit event schema if maintainers want it.
- uAgent lifecycle wrapper if it can be expressed as a platform adapter.
- Tests and fake MCP/uAgent fixtures.

## Code that should not port

- Standalone CLI wrapper as-is.
- Standalone example configs except as docs snippets.
- Private research files.
- Demo-only fake server/client beyond test fixtures.
- Agentverse account setup scripts that do not fit Hermes setup patterns.
- Version-pinning constraints that conflict with Hermes dependency policy without maintainer discussion.
- Experimental spike code.
- Any private strategy or domain-specific examples.

## Maintainer-native PR narrative

Suggested PR title:

`feat(gateway): add optional Fetch.ai uAgents platform bridge`

Suggested opening:

"This PR adds an optional Fetch.ai uAgents platform bridge for Hermes. Hermes remains the local agent/execution environment; Fetch/uAgents supplies agent identity, addressing, discovery, and agent-to-agent transport. The integration is default-deny: remote uAgent identities are treated as routing identity, not authorization, and exposed tools/actions must be explicitly allowed."

Safe claims:

- Optional bridge.
- Uses existing uAgents/MCP rails.
- Local-first and default-deny.
- Agentverse/Almanac can be used for discovery/routing when configured.
- No new payment/marketplace assumptions.

Claims to avoid:

- Do not claim generic trust in Agentverse senders.
- Do not claim full production hardening without deployment evidence.
- Do not imply Hermes endorses or owns Fetch rails.
- Do not promise unsupported wallet/payment/marketplace behavior.

## Upstream task sequence

1. Open issue/discussion first with research summary and minimal design.
2. Ask maintainers which shape they prefer: gateway platform adapter or command/plugin.
3. Add optional dependency group for `uagents` and `uagents-adapter` if accepted.
4. Port minimal adapter lifecycle and policy layer.
5. Add tests with fake uAgent/MCP or mocked uAgent runtime.
6. Add docs under Hermes docs style.
7. Add config examples with env-var placeholders only.
8. Add security notes: sender identity is not trust; default deny; seed/token handling.
9. Keep PR small. Leave Agentverse chat/ASI demos to docs or follow-up PR if maintainers want them.

## Tests for upstream PR

- Platform registration loads without Fetch deps when feature not installed.
- Missing optional deps produces clear install hint.
- Config validation rejects missing seed/unsafe public config.
- Message mapping handles inbound text/tool call requests.
- Policy denies unknown sender/tool by default.
- Redaction protects seeds/tokens/API keys in logs.
- Optional integration test can be skipped unless `HERMES_UAGENTS_E2E=1` is set.

## Docs for upstream PR

- `docs/platforms/uagents.md` or equivalent.
- Security section in the platform doc.
- Minimal local demo.
- Agentverse/Mailbox optional demo.
- Troubleshooting: missing seed, mailbox linking, ASI key absent, endpoint not reachable, version mismatch.

## Review concerns to pre-answer

- Why not a custom agent network? Because Fetch/uAgents already supplies identity/discovery/transport.
- Why not expose all Hermes tools? Because remote identities are not trust; default-deny protects operator boundaries.
- Why optional dependency? To avoid burdening Hermes installs that do not use Fetch.
- Why standalone first? To prove end-to-end behavior and avoid pushing speculative integration into Hermes core.
