# Contributing

Thank you for improving Hermes Fetch AI. This project is intentionally small: a standalone bridge, with a thin Hermes plugin, that exposes an allowlisted subset of Hermes tools to Fetch.ai uAgents with conservative security defaults.

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
uv run ruff format --check .
uv run mypy src tests
uv run pytest -q --cov
uv run python -m hermes_fetch_ai.cli demo local
rm -rf dist build
uv run python -m build
uv run python -m twine check dist/*
uv run python -m pip_audit --skip-editable --ignore-vuln CVE-2025-69277 --ignore-vuln PYSEC-2026-1325
```

Changes to `hermes-plugin/fetchai-bridge` must keep it stdlib-only. If you have a Hermes install, also run `hermes plugins validate hermes-plugin/fetchai-bridge --install-deps`; CI runs it, `hermes plugins doctor --ci`, and the stdio field test against Hermes 0.21.5 and a pinned `main`.

The `PyNaCl` and `ecdsa` ignores are tracked upstream dependency exceptions. Do not add new ignores without documenting the reason in `docs/security.md`.

`ruff` and `mypy` are pinned to a minor series so a new release cannot change the lint or type-check rules underneath CI. Dependabot proposes the bumps; fix any new findings in that PR. The package type-checks under `mypy --strict`; tests use relaxed settings (see `pyproject.toml`). CI's coverage job fails below 85% branch coverage, counting the CLI and `serve` subprocesses.

## Testing expectations

- Use TDD for security and policy behavior: failing regression first, implementation second, targeted tests third.
- Tests must be hermetic by default. No live Agentverse, Almanac, ASI, or real Hermes install in the default test run.
- Use gated tests for live Hermes checks (`HERMES_FETCH_FIELD_TEST=1`); CI's `hermes-plugin` job sets them up against pinned Hermes commits.
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
feat(plugin): pass Hermes' interpreter to the bridge
chore(ci): add CodeQL workflow
```
