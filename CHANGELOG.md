# Changelog

## 1.0.0 — 2026-06-10

First production release of the Hermes (Nous Research) x Fetch.ai bridge.

### Bridge

- Policy-aware MCP-over-uAgents bridge: signed `ListTools`/`CallTool` handlers
  with default-deny policy, sender/tool allowlists, denylist override,
  JSON-schema and SSRF argument validation, per-sender rate limits, bounded
  responses, and redacted JSONL audit.
- MCP shim backends: fake (CI), in-process Hermes tools (fallback), and the
  production-preferred hardened stdio subprocess (`shell=False`, env
  allowlist, timeouts, stderr separation).
- `serve` runs the agent on a dedicated event loop with graceful
  SIGINT/SIGTERM shutdown; proven by a two-process HTTP round-trip test with
  offline rules-based resolution.
- Hosted mode keeps uAgents' default ledger-backed registration policy so a
  funded `UAGENT_SEED`-derived wallet pays Almanac registration in FET.

### Hermes integration

- Ships as a Hermes Agent plugin (`hermes_agent.plugins` entry point):
  `hermes fetchai doctor|probe|serve|demo`, zero Hermes core changes.
- Field-tested against a real `NousResearch/hermes-agent` v0.16.x install
  (gated test `tests/test_field_hermes_stdio.py`); the Hermes tools MCP
  server's wrapped-`kwargs` argument contract is documented and asserted.
- The `hermes mcp serve` conversations/permissions surface is structurally
  out of scope.
- Upstream submission payload (optional skill + tests) validated with the
  hermes-agent harness lives in `upstream/hermes-pr/`.

### Packaging and operations

- Default config ships as package data; `demo local` and `doctor` work from
  wheel installs with no repo checkout.
- `--version` flag; CI matrix on Python 3.11/3.12; tag-driven release
  workflow building sdist and wheel.
