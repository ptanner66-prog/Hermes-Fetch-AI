# Changelog

All notable changes will be documented in this file.

This project follows semantic versioning once public releases begin.

## 1.0.0 - Unreleased

Set the date and push the `v1.0.0` tag to release.

### Fixed

- CI: pin `ruff` (0.16.x) and `mypy` (2.4.x) so new tool releases cannot change lint/type rules underneath CI; fix the findings from ruff 0.16's wider default rule set.
- `serve` now exits with status 1 and `hermes backend: FAIL: ...` when the Hermes MCP backend cannot start, instead of serving an empty tool list. A backend that dies later yields `backend unavailable` responses and audit errors instead of hung requests.
- `examples/hermes-stdio.yaml` (the production-preferred config) now uses `UAGENT_SEED` (`dev_random_seed: false`); `doctor` and `serve` warn when a config ignores a set `UAGENT_SEED`.
- Missing or malformed config files report `config: FAIL: ...` instead of a traceback; validation errors no longer echo the submitted config.
- `doctor` reads the tested dependency pins from package metadata, so they can no longer drift from `pyproject.toml`.
- `demo mailbox` works from an installed wheel (the mailbox example config is packaged); `doctor --contamination-scan` reports `SKIP` outside a source checkout instead of passing vacuously.
- Argument validation no longer treats text such as `Note: hello` as a URL.
- `hermes-local.yaml` denylists exact tool names (the old `web`/`browser`/`kanban` entries never matched anything) and matches `hermes-stdio.yaml`.
- Removed a tool-descriptor fingerprint check that compared a value with itself and could never fire.
- Docs: replaced references to deleted `research/` notes with `docs/agentverse-mailbox.md` and a design-decisions section in `docs/architecture.md`; corrected the version-specific `kwargs` argument guidance.

### Security

- Bump `mcp` to 1.28.1 (PYSEC-2026-3483), with `uagents` 0.25.3 and `uagents-core` 0.4.8.
- Require `UAGENT_SEED` to be at least 32 characters.
- Check URLs embedded anywhere in argument strings and bare local/literal-IP hosts (`localhost:8080`, `169.254.169.254/latest`); run DNS checks off the event loop.
- Scan config files for credential-shaped values inside lists and command-line args (`--api-key`, `token=...`), without flagging ordinary words such as "token".
- Cap tool error text to `max_output_bytes`; internal `CallTool` errors stay generic for callers and are logged with the audit `trace_id`.
- Document the `ecdsa` Minerva timing exception (PYSEC-2026-1325, no upstream fix) and the unauthenticated Agent Inspector endpoints in mailbox mode.
- Build with `setuptools>=83` (PYSEC-2026-3447).
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
- Release workflow can publish to PyPI through trusted publishing (opt-in via the `PUBLISH_TO_PYPI` repository variable).
- Rework the upstream Hermes submission plan for current hermes-agent rules (plugin catalog first; skill frontmatter now declares `platforms`).
