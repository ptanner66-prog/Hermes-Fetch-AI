# Contributing

Thank you for improving Hermes Fetch AI. This project is intentionally small: a standalone Hermes plugin that exposes an allowlisted subset of Hermes tools to Fetch.ai uAgents with conservative security defaults.

## Ground rules

- Keep Hermes core unchanged unless Hermes maintainers explicitly request a core PR.
- Keep the bridge default-deny.
- Do not add public tools to examples casually.
- Do not commit seeds, tokens, mailbox keys, API keys, private endpoints, or connection strings.
- Redact sensitive values as `[REDACTED]` in issues, tests, docs, and logs.
- Prefer small PRs with tests and verification evidence.

## Development setup

```bash
uv sync --extra dev
uv run python -m hermes_fetch_ai.cli doctor
uv run python -m hermes_fetch_ai.cli demo local
```

## Required local gate

Run the full gate before opening a PR:

```bash
uv run python -m hermes_fetch_ai.cli doctor
uv run python -m hermes_fetch_ai.cli doctor --contamination-scan
uv run ruff check .
uv run mypy src tests
uv run pytest -q
uv run python -m hermes_fetch_ai.cli demo local
rm -rf dist build
uv run python -m build
uv run python -m twine check dist/*
uv run python -m pip_audit --skip-editable --ignore-vuln CVE-2025-69277
```

The `PyNaCl` ignore is a tracked upstream dependency exception. Do not add new ignores without documenting the reason in `docs/security.md`.

## Testing expectations

- Use TDD for security and policy behavior: failing regression first, implementation second, targeted tests third.
- Tests must be hermetic by default. No live Agentverse, Almanac, ASI, or real Hermes install in default CI.
- Use gated tests for live Hermes checks (`HERMES_FETCH_FIELD_TEST=1`).
- Prefer behavior assertions over implementation snapshots.

## Replay metadata

`CallTool` requires `_hermes_fetch_ai` replay metadata by default. Tests and examples should use `hermes_fetch_ai.direct_protocol.replay_args(...)` unless they are explicitly testing malformed/missing metadata.

## Pull request checklist

- [ ] I ran the required local gate.
- [ ] I added or updated tests.
- [ ] I updated docs for behavior/config changes.
- [ ] I did not commit secrets or real seed material.
- [ ] I considered Windows and Unix behavior.
- [ ] I described residual risk and dependency exceptions.

## Commit style

Use Conventional Commits where practical, for example:

```text
fix(policy): reject replayed tool calls
feat(plugin): expose fetchai command group
chore(ci): add CodeQL workflow
```
