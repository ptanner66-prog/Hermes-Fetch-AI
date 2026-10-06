# Changelog

All notable changes will be documented in this file.

This project follows semantic versioning once public releases begin.

## 1.0.0 - Unreleased

Set the date and push the `v1.0.0` tag to release.

### Hermes plugin

- Added `hermes-plugin/fetchai-bridge`, a Hermes directory plugin for Hermes 0.21.5 or later. It is a stdlib-only sidecar (`python_runtime: external`) that adds `hermes fetchai-bridge`, which runs the separately installed bridge with the same arguments, and ships an `operate` skill. Settings: `command` and `uagent_seed` (a secret stored as `UAGENT_SEED`).
- `hermes_mcp.command` is optional in stdio mode when the bridge runs through the plugin: the plugin passes Hermes' interpreter and `PYTHONPATH` (`HERMES_FETCH_AI_HERMES_PYTHON`, `HERMES_FETCH_AI_HERMES_PYTHONPATH`), and the bridge starts the tools server with them, plus `HERMES_QUIET=1` and `HERMES_REDACT_SECRETS=true`, as Hermes does. An explicit `command` still wins. `examples/hermes-stdio.yaml` leaves it unset.
- The plugin keeps Hermes' Python variables (`PYTHONPATH`, `VIRTUAL_ENV`, ...) out of the bridge's environment; leaking them crashed the bridge under a managed Hermes runtime.
- `hermes backend: FAIL` now names the command to run by hand, including the one handed over by the plugin.
- New CI job `hermes-plugin`, against Hermes 0.21.5 and a pinned `main`: `hermes plugins validate --install-deps`, `hermes plugins doctor --ci`, `hermes fetchai-bridge doctor` and `demo local`, and the stdio field test.
- Removed the `hermes_agent.plugins` entry point (`hermes_fetch_ai.hermes_plugin`). It only worked with the bridge installed in Hermes' environment, which current Hermes (mcp 2.0) cannot share.
- Replaced the `optional-skills/` submission payload with a `plugin-catalog` entry draft (`upstream/hermes-pr/plugin-catalog/fetchai-bridge.yaml`) and ready-to-paste catalog PR text in `docs/upstream-hermes-pr.md`.

### Fixed

- CI: pin `ruff` (0.16.x) and `mypy` (2.4.x) so new tool releases cannot change lint/type rules underneath CI; fix the findings from ruff 0.16's wider default rule set.
- `serve` now exits with status 1 and `hermes backend: FAIL: ...` when the Hermes MCP backend cannot start, instead of serving an empty tool list. A backend that dies later yields `backend unavailable` responses and audit errors instead of hung requests.
- `examples/hermes-stdio.yaml` (the production-preferred config) now uses `UAGENT_SEED` (`dev_random_seed: false`); `doctor` and `serve` warn when a config ignores a set `UAGENT_SEED`.
- Missing or malformed config files report `config: FAIL: ...` instead of a traceback; validation errors no longer echo the submitted config.
- `doctor` reads the tested dependency pins from package metadata, so they can no longer drift from `pyproject.toml`.
- `demo mailbox` works from an installed wheel (the mailbox example config is packaged); `doctor --contamination-scan` reports `SKIP` outside a source checkout instead of passing vacuously.
- Argument validation no longer treats text such as `Note: hello` as a URL.
- `hermes-local.yaml` denylists exact tool names (the old `web`/`browser`/`kanban` entries never matched anything) and matches `hermes-stdio.yaml`; both now also deny `kanban_schedule`, `kanban_request_review`, and `kanban_request_changes`, which current Hermes exposes.
- Verified stdio mode against Hermes 0.21.5 and hermes-agent `main` (mcp 2.0); the field test follows the served schema.
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
- Verify wheel build, twine metadata, and the installed CLI (`--version`, `doctor`, `demo local`).
- Release workflow can publish to PyPI through trusted publishing (opt-in via the `PUBLISH_TO_PYPI` repository variable).
- Rework the upstream Hermes submission plan for current hermes-agent rules: a plugin catalog entry, not an in-tree skill.
