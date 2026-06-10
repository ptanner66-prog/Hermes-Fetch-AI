# Hermes Fetch AI

[![CI](https://github.com/ptanner66-prog/hermes-fetch-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/ptanner66-prog/hermes-fetch-ai/actions/workflows/ci.yml)

Hermes Fetch AI is a thin policy-aware bridge between Hermes Agent local tools and Fetch.ai uAgents. It is a connection project: Fetch supplies identity, addressing, discovery rails, envelopes, dispatcher, and uAgent protocols; Hermes supplies local execution, tool configuration, redaction, and safety boundaries.

## Status

The bridge runs an end-to-end uAgent round trip — a client uAgent sends `ListTools`/`CallTool` to the bridge uAgent over the signed MCP protocol, the bridge applies its default-deny policy, invokes the tool, and returns a bounded, audited response.

| Tier | What it proves | State |
|------|----------------|-------|
| Local end-to-end | Client uAgent → bridge uAgent → MCP tool → response, through the real uAgents in-process dispatcher | Green — run automatically in CI on Python 3.11 and 3.12 |
| Hermes-backed demo | Real Hermes tools via the Hermes tools MCP server as a hardened stdio subprocess (`examples/hermes-stdio.yaml`), `skills_list` only | Operator — needs a local `hermes-agent` install |
| Agentverse mailbox | A remote uAgent reaches the bridge over Fetch rails | Operator — needs `UAGENT_SEED` and manual Agentverse mailbox linking |

The local tier requires no secrets, hosted services, or network. Reproduce it with `python -m pytest -q` and `python -m hermes_fetch_ai.cli demo local`. The operator tiers require credentials supplied through the environment and are documented in [`docs/demo.md`](docs/demo.md).

## Quickstart

```bash
python -m pip install -e .[dev]
python -m hermes_fetch_ai.cli doctor
python -m hermes_fetch_ai.cli demo local
```

Expected local demo output includes a bridge address, visible tool count, `echo result: hello`, and audit event count.

## Hermes plugin

Installing this package into the same environment as `hermes-agent` registers a `hermes fetchai` subcommand through the `hermes_agent.plugins` entry-point group — no Hermes core changes:

```bash
pip install -e .          # alongside hermes-agent
hermes fetchai demo local
hermes fetchai serve --config examples/hermes-stdio.yaml
```

The upstream contribution plan, matched to the Hermes maintainers' PR template and contribution rubric, is in [`docs/upstream-hermes-pr.md`](docs/upstream-hermes-pr.md).

## Security defaults

- Default-deny tool calls.
- Public demo config exposes only `echo`.
- Hermes local config exposes only `skills_list` publicly.
- Sender identity is routing evidence, not authorization by itself.
- Arguments are size-limited, schema-validated, and checked for local/private URL targets and shell metacharacters.
- Outputs are size-limited with deterministic truncation.
- Audit records omit raw arguments, raw outputs, full sender addresses, seeds, tokens, and keys.
- Chat protocol is out of v1 scope.
- The bridge does not use `MCPServerAdapter.protocols` as its security boundary.

## Scope

This package does not create a new agent framework and does not implement commerce flows, exchange features, or wallet UX beyond seed/address identity needed by uAgents.
