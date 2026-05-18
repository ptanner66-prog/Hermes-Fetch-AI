# Full Connection Gap Audit

Updated: 2026-05-17T03:35:34Z

Purpose: verify that the repo is a connection project, not a reinvention project. Fetch/uAgents/Agentverse/Almanac/payment rails should supply the external agent network pieces. Hermes should supply local intelligence and operator-controlled execution. This repo should supply only the minimum bridge glue and safety policy.

## Audit table

| Surface | Upstream owner | This repo responsibility | Current status | Remaining gap |
| --- | --- | --- | --- | --- |
| Agent identity | Fetch/uAgents | Use `uagents.Agent` seed/address; do not create identity system. | Implemented. Local demos generate dev seeds; mailbox config requires operator seed. | Hosted proof needs operator seed/account. |
| Addressing and delivery | Fetch/uAgents | Route `ListTools`/`CallTool` through uAgents messages. | Implemented through bridge-owned `Protocol(spec=mcp_protocol_spec, role="server")` and local dispatcher tests. | Remote Agentverse/mailbox transcript pending. |
| Endpoint/mailbox/proxy modes | Fetch/uAgents/Agentverse | Expose config and safe startup; fail closed without seed. | Endpoint/local green; mailbox missing-seed blocker validated. | Operator must link Agentverse mailbox. |
| Protocol manifests | Fetch/uAgents/Agentverse/Almanac | Keep local publication off; document hosted manifest evidence path. | Local configs set `publish_manifest: false`. Mailbox config also keeps publication false unless operator opts in. | Hosted manifest lookup/publish evidence pending. |
| Discovery | Agentverse/Almanac | Document how to discover by digest/name; do not build marketplace. | Source sweep confirms API client manifest lookup surfaces. | Operator-hosted proof pending. |
| A2A | Fetch/uAgents adapter / A2A ecosystem | Treat as v2, not PR one. | Documented as later scope. | Needs separate package/version/public endpoint proof. |
| Payment negotiation | uAgents payment protocol models | Default disabled; dry-run request/commit/complete proof; no settlement. | Implemented and demo green. | Testnet/production settlement operator-owned. |
| Wallet/network settlement | Fetch network / wallet tooling | Do not custody wallet secrets or submit transactions. | No wallet calls implemented. | Any funded proof requires operator decision. |
| Hermes local intelligence | Hermes Agent | Call Hermes over `hermes mcp serve`; do not duplicate Hermes. | Real stdio probe/demo green through local Hermes checkout. | Upstream packaging/installation path should be made optional and clear. |
| MCP surface | Hermes MCP server | Consume MCP list/call only after bridge policy. | Implemented for fake/in-process/stdio modes; stdio verified. | SSE/HTTP modes are not enabled in local proof. |
| Tool authorization | Bridge | Default deny, public allowlist, per-sender allowlist, denylist precedence. | Implemented and tested. | Per-sender hosted policy examples need operator addresses. |
| ListTools privacy | Bridge | Filter inventory by sender and size-limit response. | Implemented and tested. Hermes stdio demo exposes 2 tools. | None locally. |
| Argument safety | Bridge | Size, schema, URL/SSRF, DNS, shell metacharacter validation. | Implemented and tested. | Tool-specific schemas rely on upstream MCP descriptors. |
| Output safety | Bridge | Normalize/truncate outputs. | Implemented and tested. | None locally. |
| Audit/logging | Bridge | Reduced audit without raw args/raw outputs/full sender addresses/secrets. | Implemented and tested. | None locally. |
| Subprocess boundary | Bridge/Hermes | `shell=False`, filtered env, stderr isolation, timeout. | Implemented and tested; Hermes stdio verified. | Upstream plugin should reuse Hermes path helpers. |
| Windows child process | Bridge/uAgents dependency interaction | Prevent cosmpy vendored protobuf path from shadowing real protobuf in spawn child. | Implemented and tested. | None locally. |
| Config | Bridge now; Hermes upstream later | Versioned YAML, reject unknown/secret-shaped values, reject chat v1. | Implemented and tested. | Upstream integration should map to Hermes config/profile conventions. |
| Plugins/upstream fit | Hermes | Future PR should be optional plugin/CLI command. | Plan updated. | Maintainer direction required. |
| Operator boundaries | Operator | Hosted account, seed, mailbox, funding, production deployment. | Documented and blocker-validated. | Operator action required. |

## Hard gaps that remain

These are not agent-solvable without crossing operator boundaries:

1. Hosted Agentverse/mailbox proof.
   - Need operator account and mailbox-capable Agentverse entry.
   - Need stable seed in the operator shell.
   - Need remote uAgent sender transcript.

2. Almanac/manifest hosted evidence.
   - Need operator opt-in if publication or registration has any fee/funding step.
   - Local CI should not publish.

3. Testnet/production settlement proof.
   - The repo proves payment message negotiation only.
   - Any funded flow must be a separate operator-approved run.

4. Upstream Hermes PR.
   - No upstream branch was opened in this run.
   - Shape should be confirmed before touching the dirty local Hermes checkout.

## Agent-solvable gaps closed

The previous MOE status did not meet acceptance because the reports and final verification were incomplete. This continuation closed those local gaps:

- Required reports written.
- Fetch GitHub sweep refreshed.
- Hermes upstream sweep refreshed.
- Full connection audit written.
- Teknium one-pager written.
- Upstream plan updated.
- Full pytest/ruff/mypy/doctor gates green.
- Hermes stdio probe and demo green.
- Local demo green.
- Payment dry-run demo green.
- Mailbox missing-seed blocker validated.

## Thin-bridge conclusion

The repo should stay small. The durable value is the safety and policy membrane between Fetch's agent network rails and Hermes' local execution surface:

- Fetch side: identity, address, transport, mailbox, discovery, manifest, payment protocol messages.
- Hermes side: local agent, MCP server, tools, plugins, config, logs, operator approvals.
- Bridge side: explicit policy, validation, redaction, demo/docs/tests, and careful defaults.

Anything beyond that belongs in a follow-up only if maintainers ask for it.
