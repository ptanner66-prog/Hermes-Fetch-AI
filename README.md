# Hermes Fetch AI

Hermes Fetch AI is a thin policy-aware bridge between Hermes Agent local tools and Fetch.ai uAgents. It is a connection project: Fetch supplies identity, addressing, discovery rails, envelopes, dispatcher, and uAgent protocols; Hermes supplies local execution, tool configuration, redaction, and safety boundaries.

## Quickstart

```bash
python -m pip install -e .[dev]
python -m hermes_fetch_ai.cli doctor
python -m hermes_fetch_ai.cli demo local
```

Expected local demo output includes a bridge address, visible tool count, `echo result: hello`, and audit event count.

To prove the real Hermes stdio MCP hookup after Hermes is installed on PATH:

```bash
python -m hermes_fetch_ai.cli doctor --config examples/hermes-stdio.yaml --probe-backend
python -m hermes_fetch_ai.cli demo hermes --config examples/hermes-stdio.yaml
```

## Security defaults

- Default-deny tool calls.
- Public demo config exposes only `echo`.
- Hermes stdio demo config exposes only low-risk read/poll tools publicly and denies side-effecting send/approval tools.
- Sender identity is routing evidence, not authorization by itself.
- Arguments are size-limited, schema-validated, and checked for local/private URL targets and shell metacharacters.
- Outputs are size-limited with deterministic truncation.
- Audit records omit raw arguments, raw outputs, full sender addresses, seeds, tokens, and keys.
- Chat protocol is out of v1 scope.
- The bridge does not use `MCPServerAdapter.protocols` as its security boundary.

## Scope

This package does not create a new agent framework. Payment protocol support is optional, disabled by default, and limited in this proof to source-backed dry-run negotiation. Testnet/sandbox and real-value settlement require separate operator approval and runbooks. This proof does not move real FET, custody wallet secrets, or build exchange features or broad marketplace sprawl.

## Docs

- [Hermes Fetch uAgents bridge](docs/fetch-uagents-bridge.md)
- [Agentverse hosted proof boundaries](docs/agentverse-hosted-proof.md)
- [Agentverse operator handoff](docs/agentverse-operator-handoff.md)
- [Payment rails and proof levels](docs/payment-rails.md)
- [Agentic economy thesis](docs/agentic-economy-thesis.md)
