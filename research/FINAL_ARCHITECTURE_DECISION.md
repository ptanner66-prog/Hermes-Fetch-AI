# Final Architecture Decision

Date accessed: 2026-05-17
Status: current after MOE hardening continuation. This file supersedes older notes that treated `hermes mcp serve` as spike-only.

## Final architecture

Hermes Fetch AI v1 is a standalone Python package that exposes a narrow, policy-aware MCP-over-uAgents bridge.

The bridge owns exactly one core uAgents protocol for v1:

- `Protocol(spec=mcp_protocol_spec, role="server")`
- message models imported from `uagents_adapter.mcp.protocol`:
  - `ListTools`
  - `ListToolsResponse`
  - `CallTool`
  - `CallToolResponse`
  - `mcp_protocol_spec`

The bridge does not treat upstream adapter defaults or chat protocol wiring as the security boundary. It uses the official MCP protocol message models and applies its own policy, validation, and audit controls before calling Hermes.

## Runtime layers

1. Fetch/uAgents layer
   - identity, addresses, signed envelopes, local dispatcher, endpoint/mailbox/proxy modes, optional Agentverse/Almanac rails, and protocol manifests.

2. Bridge layer
   - versioned config, sender/tool policy, filtered tool inventory, argument validation, rate limits, result normalization, redacted audit logs, demos, and tests.

3. MCP/Hermes layer
   - fake MCP server for CI, optional in-process compatibility path, and real stdio MCP client path to `hermes mcp serve`.

4. Hermes local execution
   - Hermes owns local tools, MCP server, plugins, config, logging, skills, and operator boundaries.

## Why existing rails are enough

Fetch/uAgents already provide:

- cryptographic agent identity and addresses;
- signed message routing;
- in-process dispatcher for deterministic local two-agent tests;
- endpoint, mailbox, and proxy modes;
- optional Agentverse/Almanac discovery and manifests;
- `Protocol(spec=..., role="server")` role binding;
- published MCP protocol message models/spec through `uagents_adapter.mcp.protocol`.

MCP already provides:

- `ClientSession.list_tools()` returning available tools;
- `ClientSession.call_tool()` returning tool results;
- stdio client transport used by this repo's Hermes proof;
- stable result shapes under the pinned `mcp==1.27.1` environment.

Hermes already provides:

- local tool registry and dispatch;
- `hermes mcp serve` as a stdio MCP server;
- plugin/config/logging conventions;
- local operator-controlled execution.

Therefore this repo does not need a new agent framework, new identity system, new discovery layer, chat implementation, wallet UX, or marketplace. It adds only the missing trust-boundary glue plus optional, default-off payment negotiation rails that use uAgents message models without settlement.

## Exact thin layer this repo adds

Package: `hermes-fetch-ai`.

Key modules:

- `config.py`: versioned YAML/env config; rejects unknown fields, secret-shaped YAML values, `chat.enable_chat=true`, missing stdio command, and mailbox mode without a stable operator seed.
- `policy.py`: default-deny policy, sender/tool allowlists, denylist override, and per-sender rate limits.
- `arg_validator.py`: JSON schema validation and URL/SSRF/shell-metacharacter guards before invocation.
- `result_normalizer.py`: normalizes MCP/FastMCP result shapes into `NormalizedToolResult`.
- `mcp_shim.py`: owns MCP lifecycle for fake, in-process compatibility, and stdio modes; stdio uses `shell=False`, filtered env, timeout, and stderr separation.
- `fake_mcp.py`: fake FastMCP builder for CI/local demo.
- `direct_protocol.py`: bridge-owned signed-message protocol handlers.
- `uagent_app.py`: constructs `uagents.Agent`, includes only bridge protocols, applies no-op registration for local configs, and hardens Windows child startup against the cosmpy/protobuf path collision.
- `registration_policies.py`: `NoopRegistrationPolicy` for offline CI.
- `_redaction.py`, `audit.py`: redacted reduced audit without raw args, raw outputs, full sender addresses, or secrets.
- `payment_policy.py`, `payment_protocol.py`, `payments.py`: default-off payment negotiation/dry-run support using official uAgents payment models.
- `hermes_probe.py`: probes local Hermes/MCP availability.
- `cli.py`: `doctor`, `probe-hermes`, `serve`, `demo local`, `demo hermes`, `demo mailbox`, `demo payment-dry-run`.

## Exact message flow

### Local CI flow

1. Demo/test creates bridge and client agents in one Python process.
2. Both use testnet, no-op registration, no Agentverse inspector, and no manifest publication.
3. Bridge starts `HermesMCPClientShim(mode="fake")`.
4. Bridge includes `direct_protocol.build_protocol(...)`.
5. Client sends `ListTools`; bridge filters the inventory by policy and returns `ListToolsResponse`.
6. Client sends `CallTool(tool="echo", args={"text":"hello"})`.
7. Bridge checks size, rate limit, authorization, schema, URL/SSRF, shell metacharacters, tool descriptor stability, and only then calls the shim.
8. Bridge normalizes result, audits reduced metadata, and returns `CallToolResponse`.

### Hermes stdio local demo flow

1. Operator points `HERMES_FETCH_HERMES_PYTHON` at a local Hermes checkout Python or installs a `hermes` console script that can run `hermes mcp serve`.
2. Config uses `hermes_mcp.mode: stdio`.
3. Shim starts the Hermes MCP server through stdio with `shell=False`, filtered environment, timeout, and stderr separated from protocol stdout.
4. Policy exposes only low-risk read/poll tools in the demo (`conversations_list`, `events_poll`) and denies side-effecting send/approval tools.
5. The bridge demo calls `conversations_list` through the same uAgents/MCP protocol path used by the fake local demo.

### Agentverse/mailbox manual demo flow

1. Operator sets `UAGENT_SEED` outside the repo.
2. Operator runs `python -m hermes_fetch_ai.cli demo mailbox --config examples/agentverse-mailbox-hermes.yaml` or `serve --config examples/agentverse-mailbox-hermes.yaml`.
3. Config uses testnet mailbox mode and keeps manifest publication/inspector off by default unless the operator explicitly opts in.
4. Operator links mailbox in Agentverse UI.
5. Remote uAgent sends `ListTools`/`CallTool` using the same MCP protocol messages.
6. The exact same bridge policy path handles the request.

### Payment dry-run flow

1. Config keeps `payment.mode: disabled` by default.
2. Dry-run config sets `payment.mode: dry_run` and priced tools.
3. The demo creates a `RequestPayment`, commits a `dryrun-*` transaction id, and returns `CompletePayment`.
4. Payment status does not override authorization; tool policy and argument validation remain mandatory.
5. No wallet calls or settlement are performed.

## Trust boundaries

Boundary 1: remote uAgent to uAgents runtime.

- uAgents signed message handling supplies routing identity.
- Sender address is not sufficient authorization.

Boundary 2: uAgents runtime to bridge policy handlers.

- Only bridge-owned `ListTools` and `CallTool` handlers are in scope.
- List and call surfaces are both authorization surfaces.
- Unknown senders see only configured public tools or an empty list.

Boundary 3: bridge policy to MCP shim.

- Denied calls never invoke the shim.
- Args are size-checked and schema-validated before shim call.
- URL-like args are checked before shim call.
- Per-sender rate limits apply before expensive operations.
- Tool descriptor fingerprint is rechecked before invocation.

Boundary 4: MCP shim to Hermes/local subprocess.

- Stdio uses static command/args from config, no shell, filtered env, timeout, and stderr separation.
- Output is normalized and truncated before returning over uAgents.

Boundary 5: logs/audit.

- Audit records decisions, sizes, truncation, durations, payment metadata, and error classes.
- Audit does not record raw args, raw outputs, seeds, tokens, prompts, or full sender addresses.

## Exact local verification status

Commands run in the MOE continuation:

```text
cmd //c ".\\.venv\\Scripts\\python.exe -m pytest -q"
cmd //c ".\\.venv\\Scripts\\python.exe -m ruff check ."
cmd //c ".\\.venv\\Scripts\\python.exe -m mypy src\\hermes_fetch_ai --ignore-missing-imports"
cmd //c ".\\.venv\\Scripts\\python.exe -m hermes_fetch_ai.cli doctor --contamination-scan"
cmd //c ".\\.venv\\Scripts\\python.exe -m hermes_fetch_ai.cli doctor --config examples\\hermes-stdio-env.yaml --probe-backend"
cmd //c ".\\.venv\\Scripts\\python.exe -m hermes_fetch_ai.cli demo hermes --config examples\\hermes-stdio-env.yaml"
cmd //c ".\\.venv\\Scripts\\python.exe -m hermes_fetch_ai.cli demo local"
cmd //c ".\\.venv\\Scripts\\python.exe -m hermes_fetch_ai.cli demo payment-dry-run --config examples\\payment-dry-run.yaml"
```

Observed:

- `77 passed in 17.94s`
- `All checks passed!`
- `Success: no issues found in 20 source files`
- `contamination: ok`; `doctor: ok`
- Hermes stdio backend: `backend: ok: 10 tools`
- Hermes stdio demo returned empty `conversations_list` through the bridge
- local fake demo returned `echo result: hello`
- payment dry-run returned `CompletePayment`

## Dependency pins

Final v1 reproducibility pins:

- `uagents==0.24.2`
- `uagents-core==0.4.4`
- `uagents-adapter[mcp]==0.6.2`
- `mcp==1.27.1`
- `pydantic>=2.8,<3`
- `PyYAML>=6,<7`
- `python-dotenv>=1.0,<2`
- `jsonschema>=4.20,<5`
- `httpx>=0.25,<1`
- dev: `pytest>=8,<9`, `pytest-asyncio>=0.23,<1`, `anyio>=4,<5`, `ruff>=0.5`, `mypy>=1.10`

## Final confidence level

- Local CI fake-MCP direct uAgent demo: green.
- Real Hermes stdio MCP bridge: green locally against the source checkout venv.
- Payment dry-run negotiation: green locally.
- Agentverse mailbox/manual hosted proof: blocked on operator account/seed/linking.
- Upstream Hermes PR shape: ready for maintainer direction; no PR opened in this run.

## Final decision

Proceed with a narrow upstream conversation around an optional Hermes plugin/CLI bridge. Do not add A2A, wallet settlement, hosted account automation, or broad marketplace UX to PR one unless maintainers request that scope.
