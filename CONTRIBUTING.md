# Contributing

Thank you for improving Hermes Fetch AI. The project is deliberately small: a standalone bridge, with a thin Hermes plugin, that lets Fetch.ai uAgents call an allowlisted subset of Hermes tools with conservative security defaults.

## Ground rules

- Keep the bridge default-deny, and do not make tools public in the examples without a reason.
- Keep Hermes core unchanged; the bridge talks to Hermes only through its tools MCP server.
- Never commit seeds, tokens, mailbox keys, API keys, private endpoints, or connection strings. Write `[REDACTED]` in issues, tests, docs, and logs.
- Prefer small pull requests with tests and the output of the local gate.

Report vulnerabilities privately, as described in [`SECURITY.md`](SECURITY.md), not in a public issue.

## Development setup

Python 3.11 or 3.12:

```bash
uv sync --extra dev
uv run hermes-fetch-ai doctor
uv run hermes-fetch-ai demo local
```

With pip: `python -m pip install -e ".[dev]"`.

## Local gate

Run this before opening a pull request; CI runs the same checks on Linux, macOS, and Windows:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest -q --cov --cov-fail-under=90
uv run hermes-fetch-ai demo local
rm -rf dist build
uv run python -m build
uv run python -m twine check dist/*
uv run python -m pip_audit --skip-editable --ignore-vuln CVE-2025-69277 --ignore-vuln PYSEC-2026-1325
```

- Coverage is branch coverage and counts the CLI and `serve` subprocesses that the tests start.
- The package type-checks under `mypy --strict`; tests use relaxed settings (see `pyproject.toml`).
- `ruff` and `mypy` are pinned to a minor series, so a new release cannot change the rules underneath CI. Dependabot proposes the bumps; fix any new findings in that pull request.
- The two `pip_audit` ignores are documented in [`docs/security.md`](docs/security.md#residual-risks). Do not add one without documenting it there.

Changes to `hermes-plugin/fetchai-bridge` must keep it stdlib-only. If you have a Hermes install, also run `hermes plugins validate hermes-plugin/fetchai-bridge --install-deps`. CI runs that, `hermes plugins doctor --ci`, the plugin's CLI, and the field test against Hermes 0.21.5 and a pinned `main`.

## Tests

- For security and policy changes, write the failing test first.
- The default test run is hermetic: no Agentverse, Almanac, or Hermes install, and it passes with networking disabled (only loopback). The `almanac_calls` fixture in `tests/conftest.py` records Almanac contacts, so tests can check that a private bridge makes none.
- Tests against a real Hermes install are opt-in (`HERMES_FETCH_FIELD_TEST=1`); [`docs/demo.md`](docs/demo.md#field-test-against-a-real-hermes-agent-install) shows how to run them.
- Tests against Fetch's real testnet are opt-in too: `HERMES_FETCH_LIVE_TESTNET=1 pytest tests/test_live_testnet.py`. They read Dorado's ledger, get test FET from Fetch's faucet into a wallet made for the run (or use the buying wallet of `HERMES_FETCH_PAYER_SEED`), pay a `serve` bridge and a chat seller for real, and search Agentverse (with `HERMES_FETCH_LIVE_AGENTVERSE_API_KEY` if set). A run spends about 0.06 test FET and takes a few minutes. On GitHub, the "Live testnet" workflow runs them by hand only; its optional secrets go in the repository's `testnet` environment.
- `tests/test_protocol_canaries.py` pins Fetch's protocol digests and the message fields the bridge and ASI:One use, and checks that the Agentverse listing names exactly the protocols the agent speaks. A uAgents upgrade that changes them fails there first.
- A test may connect only to this machine; the guard in `tests/conftest.py` fails any other connection, also through a proxy, unless the test is marked `network`. gRPC opens its own sockets, which the guard cannot see, so tests that build plain uAgents agents use the `almanac_calls` fixture.
- `tests/test_contamination.py` keeps the public tree on topic.
- Test behavior, not implementation details.
- Calls in tests and examples carry replay-protection metadata from `hermes_fetch_ai.direct_protocol.replay_args(...)`, unless the test is about missing or malformed metadata.

## Pull requests

Fill in the pull request template. Update the docs and `CHANGELOG.md` when behavior or configuration changes, and say what residual risk a change leaves.

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):

```text
fix(policy): reject replayed tool calls
feat(plugin): pass Hermes' interpreter to the bridge
ci: add CodeQL workflow
```
