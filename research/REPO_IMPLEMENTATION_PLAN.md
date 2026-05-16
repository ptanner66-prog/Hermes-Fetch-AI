# Repository Implementation Plan

Date accessed: 2026-05-16

## Goal

Build a standalone private-first `hermes-fetch-ai` repo that proves Hermes can be exposed as a discoverable/callable Fetch.ai uAgent through existing Fetch/uAgents and MCP rails. Keep reusable bridge logic cleanly separated from runner/demo code so a later upstream Hermes PR can port only the Hermes-native slice.

## Proposed file tree

```text
hermes-fetch-ai/
  pyproject.toml
  README.md
  LICENSE
  .gitignore
  .env.example
  src/hermes_fetch_ai/
    __init__.py
    cli.py
    config.py
    logging.py
    policy.py
    audit.py
    mcp_shim.py
    adapter_runner.py
    result_normalizer.py
    uagent_app.py
    hermes_probe.py
    version_pins.py
  examples/
    local-direct.yaml
    agentverse-mailbox.yaml
    public-endpoint.yaml
    fake_mcp_server.py
    local_client.py
    README.md
  tests/
    conftest.py
    test_config.py
    test_policy.py
    test_result_normalizer.py
    test_mcp_shim_fake_server.py
    test_uagent_direct_protocol.py
    test_security_defaults.py
  docs/
    architecture.md
    security.md
    demo.md
    troubleshooting.md
    upstream-hermes-pr.md
  research/
    RESEARCH_INDEX.md
    ARCHITECTURE_DECISION.md
    HERMES_MCP_SURFACE.md
    FETCH_UAGENTS_SURFACE.md
    MCP_ADAPTER_SPIKE_PLAN.md
    E2E_DEMO_PLAN.md
    REPO_IMPLEMENTATION_PLAN.md
    UPSTREAM_PR_PLAN.md
    SECURITY_MODEL.md
    V1_SCOPE.md
    PUBLIC_POSITIONING.md
    OPEN_QUESTIONS.md
    BUILD_PROMPT.md
    CONTAMINATION_AUDIT.md
```

## Module responsibilities

### `config.py`

- Load YAML config plus environment variables.
- Required env: `UAGENT_SEED` unless `dev_random_seed: true` is explicit.
- Optional env: `ASI1_API_KEY`, Agentverse token if needed, Hermes command override.
- Validate no secrets are in checked-in example configs.
- Config sections:
  - `agent`: name, port, endpoint/mailbox/proxy, description/readme metadata.
  - `hermes_mcp`: mode (`stdio`, `url`, `in_process_hermes_tools`, `fake`), command/args/url, timeout.
  - `policy`: allowed senders, public tools, allowed tools, denied tools, side-effect gates, payload/output caps.
  - `logging`: audit path, redaction, verbosity.

### `mcp_shim.py`

- Implement `HermesMCPClientShim` object with async `list_tools()` and `call_tool()` methods suitable for a bridge-owned direct uAgent protocol.
- Treat `MCPServerAdapter` as a reference for message shapes and optional chat/demo work, not as the default security boundary.
- Support stdio first with official MCP SDK `ClientSession`, `StdioServerParameters`, and `stdio_client`.
- Optional later support for streamable HTTP/SSE.
- Expose async `list_tools()` and `call_tool(name, args)`.
- Provide `run(transport="stdio")` no-op/guard for adapter compatibility.
- Lifecycle methods: `start()`, `close()`, async context manager.
- Reconnect after server death only if safe and bounded.

### `result_normalizer.py`

- Convert MCP `CallToolResult` into adapter-friendly string/JSON.
- Handle text content, image/binary/resource content, structured content, `isError`, and oversized outputs.
- Preserve enough error detail for debugging without exposing secrets.

### `policy.py`

- Enforce sender/tool/payload policies before MCP calls.
- Treat `sender` addresses as identity, not trust.
- Default deny all tools unless explicitly allowed.
- Allow a tiny public-safe set for demos, preferably fake echo/status until Hermes-safe tools are verified.
- Side-effect tools require explicit sender allowlist and optional operator approval hook later.

### `audit.py` and `logging.py`

- Structured JSONL audit logs.
- Redact secrets by default.
- Record: timestamp, sender, protocol, tool, decision, reason, duration, payload size, output size, error type, trace id.
- Do not log raw seeds, tokens, ASI keys, full prompts, or full tool outputs by default.

### `uagent_app.py`

- Construct `uagents.Agent` with config.
- Construct `HermesMCPClientShim` or fake/in-process MCP object.
- Include a bridge-owned, policy-aware direct `ListTools`/`CallTool` protocol with `publish_manifest=True`.
- Do not publish unmodified `MCPServerAdapter.protocols` by default, because sender-aware authorization and sender-filtered tool inventory must run before shim/MCP access.
- Ensure direct protocol can run without ASI key; do not publish chat unless explicitly enabled and keyed.
- Own startup/shutdown wiring.

### `direct_protocol.py`

- Define/import message models compatible with the direct adapter rail: `ListTools`, `CallTool`, response/error types.
- Handlers must receive `sender`, filter `ListTools` per sender, authorize `CallTool` per sender/tool/args, and audit allow/deny before shim access.
- Denied calls must not invoke shim/MCP.
- Document exact protocol choice with tests.

### `hermes_probe.py`

- Probe Hermes availability:
  - `hermes --version`.
  - `hermes mcp serve --help`.
  - try stdio MCP initialize/list with timeout.
  - try `_build_server()` fallback only in explicit mode.
- Print actionable diagnosis.

### `cli.py`

Commands:

```text
hermes-fetch-ai doctor
hermes-fetch-ai probe-hermes
hermes-fetch-ai serve --config examples/local-direct.yaml
hermes-fetch-ai demo local
hermes-fetch-ai demo mailbox
```

## Tests

Minimum test matrix:

- Config loads env and refuses missing seed outside dev mode.
- `.env.example` contains names only, no real values.
- Policy denies unknown tools by default.
- Policy denies side-effect tools for unknown sender.
- Result normalizer handles text, structured content, errors, oversized outputs.
- Shim lists/calls fake MCP server.
- Bridge direct local uAgent protocol returns fake echo result.
- Chat protocol is skipped unless `ASI1_API_KEY` present.
- Audit logs redact token-like strings.
- Contamination scan passes required terms.

Recommended commands:

```bash
python -m pytest -q
python -m ruff check .
python -m mypy src/hermes_fetch_ai --ignore-missing-imports
python -m hermes_fetch_ai.cli doctor
```

## Security defaults

- Default deny external tool calls.
- Seed required from env/secret manager.
- No secrets in config examples.
- Redacted structured logs.
- Max payload bytes and max output chars.
- Per-call timeout.
- Sender allowlist for non-public tools.
- Disable filesystem/terminal/shell tools unless explicitly configured by operator.
- Treat Agentverse/uAgent identity as routing identity, not trust.
- No public endpoint instructions before local and mailbox demos pass.

## Build order

1. Package skeleton and pins.
2. Fake MCP server and result normalizer tests.
3. Policy and audit tests.
4. MCP shim against fake stdio server.
5. Adapter integration with in-process official FastMCP echo.
6. Local two-uAgent direct protocol E2E.
7. Hermes probe command.
8. Hermes-backed direct demo using `hermes mcp serve` or `_build_server()` fallback.
9. Mailbox/Agentverse optional demo.
10. Docs/readme/security/troubleshooting.
11. Contamination scan and release checklist.

## What not to build in v1

- Payments, billing, marketplace pricing.
- Wallet UX beyond seed/address identity requirements.
- Per-skill commercial manifests.
- Broad public tool exposure.
- Domain-specific use cases.
- Custom agent network/discovery protocol.
- Complex orchestration beyond request/response bridge.
