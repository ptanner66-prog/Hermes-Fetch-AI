# Changelog

All notable changes will be documented in this file.

This project follows semantic versioning once public releases begin.

## Unreleased

### Security

- Reject local/private/non-global/reserved URL targets and DNS resolutions in tool arguments.
- Reject shell-control characters and unsafe shell metacharacters unless explicitly trusted.
- Require bridge replay/idempotency metadata for `CallTool` by default.
- Add bounded TTL replay cache for duplicate/stale/future call rejection.
- Add global and bounded per-sender rate limiting for tool calls and tool listing.
- Enforce environment-only production `UAGENT_SEED`; reject production YAML seed material.
- Strengthen redaction for multi-word sensitive values.
- Ensure normalized output never exceeds configured byte cap.

### Reliability

- Make real HTTP serve smoke use a dynamic port and separate subprocess.
- Make serve shutdown deterministic on Windows and Unix.
- Add audit metadata that reflects normalized truncation/original-byte state.

### Open source readiness

- Add stronger CI matrix, security audit, package verification, CodeQL, and Dependabot.
- Add native Hermes plugin documentation and founder/open-source governance docs.
- Verify wheel build, twine metadata, and plugin entry point discovery.
