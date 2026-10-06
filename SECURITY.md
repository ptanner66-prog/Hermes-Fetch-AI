# Security Policy

## Supported versions

No release has been tagged yet. Until `v1.0.0` ships, fixes land on `main` only; after that, the latest release and `main` are supported.

## Reporting a vulnerability

Report privately at <https://github.com/ptanner66-prog/Hermes-Fetch-AI/security/advisories/new>. Do not open a public issue.

Please include:

- the affected commit or version;
- steps to reproduce, safe to run;
- the expected impact;
- whether it needs secrets, hosted Agentverse state, or a local Hermes install;
- logs, with every secret replaced by `[REDACTED]`.

Never send real seeds, tokens, mailbox keys, API keys, private endpoints, or connection strings.

The project has one maintainer. Expect an acknowledgement within a few days, a fix on a private branch (or a documented mitigation if no code change can help), and a published advisory once the fix is available.

## Security model

The bridge is default-deny. It exposes a policy-filtered subset of Hermes tools to signed uAgent messages, with replay protection, rate limits, schema and URL/shell argument checks, size-capped output, a redacted audit log, and seeds read only from the environment. It uses Hermes' tools MCP server only, never the conversations and messaging surface. The threat model, controls, and residual risks are in [`docs/security.md`](docs/security.md).
