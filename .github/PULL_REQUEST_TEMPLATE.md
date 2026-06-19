## Summary

<!-- What changed and why? -->

## Security / safety impact

- [ ] No new network exposure by default
- [ ] Default-deny policy preserved
- [ ] No secrets or seed material committed
- [ ] Replay/rate-limit/validation/redaction impact considered

## Verification

Paste the commands you ran and their results:

```text
uv run python -m hermes_fetch_ai.cli doctor
uv run python -m hermes_fetch_ai.cli doctor --contamination-scan
uv run ruff check .
uv run mypy src tests
uv run pytest -q
uv run python -m hermes_fetch_ai.cli demo local
rm -rf dist build
uv run python -m build
uv run python -m twine check dist/*
```

## Docs

- [ ] README/docs updated if behavior changed
- [ ] SECURITY/docs updated if risk changed
- [ ] CHANGELOG updated

## Release notes

<!-- User-facing impact, migration notes, residual risk. -->
