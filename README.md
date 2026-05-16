# Hermes Fetch AI

Hermes Fetch AI is a thin policy-aware bridge between Hermes Agent local tools and Fetch.ai uAgents. It is a connection project: Fetch supplies identity, addressing, discovery rails, envelopes, dispatcher, and uAgent protocols; Hermes supplies local execution, tool configuration, redaction, and safety boundaries.

## Quickstart

```bash
python -m pip install -e .[dev]
python -m hermes_fetch_ai.cli doctor
python -m hermes_fetch_ai.cli demo local
```

Expected local demo output includes a bridge address, visible tool count, `echo result: hello`, and audit event count.

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
