# Security Policy

## Supported versions

This repository is pre-1.1 and hardening-focused. Security fixes target `main` and the latest tagged release once releases begin.

| Version | Supported |
| --- | --- |
| `main` | Yes |
| Latest release | Yes |
| Older commits/tags | Best effort only |

## Reporting a vulnerability

Please do not open a public issue for a vulnerability report.

Use GitHub Security Advisories if available, or contact the repository owner privately with:

- affected commit/version;
- safe reproduction steps;
- expected impact;
- whether the issue requires secrets, hosted Agentverse state, or a local Hermes install;
- logs with all secrets replaced by `[REDACTED]`.

Never send real seeds, tokens, mailbox keys, API keys, private endpoints, or connection strings.

Expected maintainer response:

1. Acknowledge within 72 hours.
2. Confirm severity and affected versions.
3. Patch on a private branch or publish a mitigation if no code change is possible.
4. Release and disclose after the fix is available.

## Security model summary

Hermes Fetch AI is default-deny. It exposes a policy-filtered subset of Hermes tools to signed uAgent messages and applies replay protection, global/per-sender rate limiting, schema validation, URL/shell-input guards, bounded output, redacted audit, and environment-only production seed loading.

The bridge targets the Hermes tools MCP server only. The Hermes conversations/messaging MCP surface is out of scope and must not be exposed through this bridge.

See `docs/security.md` for the full threat model and residual dependency exceptions.
