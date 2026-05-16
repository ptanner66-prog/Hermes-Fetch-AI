# Build Prompt

You are continuing in the Hermes Fetch AI repository.

Working directory:
C:\Users\ptann\OneDrive\Work\Hermes Fetch AI

Mission:
Build the standalone private-first Hermes Fetch AI bridge. The repository should prove Hermes Agent can be exposed as a Fetch.ai uAgent through existing uAgents / Agentverse / Almanac / MCP rails, with narrow scope and strong safety defaults. Do not build a new agent network or marketplace. Build the thinnest reliable bridge.

Hard exclusions:
- Do not include OpenClaw architecture, references, examples, README language, implementation plans, or source material.
- Do not include legal-tech/domain-specific examples or private workflow content.
- Do not build payments, billing, marketplace pricing, wallet UX beyond minimum seed/address identity, or per-skill commercial manifests.
- Do not commit `.env`, secrets, caches, logs, virtualenvs, `node_modules`, credentials, package dumps, or unrelated project files.

Evidence to read first:
- `research/RESEARCH_INDEX.md`
- `research/ARCHITECTURE_DECISION.md`
- `research/HERMES_MCP_SURFACE.md`
- `research/FETCH_UAGENTS_SURFACE.md`
- `research/MCP_ADAPTER_SPIKE_PLAN.md`
- `research/E2E_DEMO_PLAN.md`
- `research/SECURITY_MODEL.md`
- `research/REPO_IMPLEMENTATION_PLAN.md`
- `research/UPSTREAM_PR_PLAN.md`
- `research/V1_SCOPE.md`
- `research/CONTAMINATION_AUDIT.md`

Architecture decision:
Use existing rails first, but do not publish `MCPServerAdapter.protocols` wholesale by default. `uagents-adapter==0.6.2` is strong evidence that MCP-shaped tools can be mapped onto uAgent protocols, but its direct handlers receive `sender` and then call `self.mcp.list_tools()` / `self.mcp.call_tool(...)` without passing sender into the MCP object. A sender-blind shim cannot enforce sender-aware authorization or sender-filtered tool inventory.

Therefore v1 must build a small policy-aware direct uAgent protocol in this repo, reusing the adapter message shapes/imports where practical, and route calls into `HermesMCPClientShim` only after bridge policy authorizes the sender/tool/action. Treat `uagents-adapter` as a reference rail and optional chat/demo dependency, not as the unmodified security boundary.

Version baseline:
- Python >= 3.11
- `uagents==0.24.2`
- `uagents-core==0.4.4`
- `uagents-adapter==0.6.2` for message-shape/reference compatibility; do not rely on unmodified protocols for secure v1
- `mcp==1.27.1` for MCP client transports, while documenting Hermes package compatibility probes because Hermes research observed `mcp==1.26.0` in a dev-extra context
- `pydantic>=2.8,<3`
- `python-dotenv`
- test deps: `pytest`, `pytest-asyncio`
- optional lint/type tools if available: `ruff`, `mypy`

Build file tree:

```text
pyproject.toml
README.md
.env.example
src/hermes_fetch_ai/__init__.py
src/hermes_fetch_ai/cli.py
src/hermes_fetch_ai/config.py
src/hermes_fetch_ai/logging.py
src/hermes_fetch_ai/audit.py
src/hermes_fetch_ai/policy.py
src/hermes_fetch_ai/result_normalizer.py
src/hermes_fetch_ai/mcp_shim.py
src/hermes_fetch_ai/direct_protocol.py
src/hermes_fetch_ai/uagent_app.py
src/hermes_fetch_ai/hermes_probe.py
examples/local-direct.yaml
examples/agentverse-mailbox.yaml
examples/fake_mcp_server.py
examples/local_client.py
tests/conftest.py
tests/test_config.py
tests/test_policy.py
tests/test_result_normalizer.py
tests/test_mcp_shim_fake_server.py
tests/test_direct_protocol_policy.py
tests/test_uagent_direct_protocol.py
tests/test_security_defaults.py
docs/architecture.md
docs/security.md
docs/demo.md
docs/troubleshooting.md
docs/upstream-hermes-pr.md
```

Implementation tasks:

1. Create package skeleton and pinned dependencies.
2. Implement config loader:
   - YAML + env support.
   - Required `UAGENT_SEED` unless `dev_random_seed: true`.
   - Config sections: `agent`, `hermes_mcp`, `policy`, `logging`, optional `chat`.
   - Examples contain placeholders only.
3. Implement redacted structured logging/audit:
   - JSONL audit events.
   - redact token/secret-like strings.
   - log sender address, protocol, decision, tool, sizes, errors, durations, and hashes/truncated snippets only; not full secrets/prompts/tool payloads/tool outputs by default.
   - do not emit raw adapter logger records that contain prompts, schemas, args, responses, or tool outputs.
4. Implement policy layer:
   - default deny all Hermes tools.
   - explicit public tools list for unknown senders; default should be empty or fake/status-only.
   - explicit sender allowlists for non-public tools.
   - sender-filtered `ListTools`: unknown senders cannot enumerate non-public Hermes tools or schemas.
   - max payload bytes, max output chars, timeout config.
   - deny side-effecting tools unless explicitly configured for that sender/tool.
5. Implement `result_normalizer.py`:
   - normalize MCP text content, structured content, errors, and oversized output to deterministic string/JSON.
6. Implement `mcp_shim.py`:
   - official SDK stdio client first.
   - async `list_tools()` and `call_tool()`.
   - safe `run(transport="stdio")` compatibility method only if needed for demos; it must not start an extra foreground MCP server.
   - `start()`/`close()` and bounded timeout handling.
7. Implement fake MCP server and tests.
8. Implement `direct_protocol.py`:
   - define/import the direct MCP message models compatible with Fetch/uAgents adapter expectations: `ListTools`, `CallTool`, `ToolResponse`, and errors as needed.
   - create a `uagents.Protocol` with handlers that receive `sender` from uAgents.
   - on `ListTools`, call `shim.list_tools()`, filter tool inventory through `policy.visible_tools(sender, tools)`, redact/audit, then respond.
   - on `CallTool`, validate payload size and schema shape, call `policy.authorize(sender, tool, args, protocol="direct_mcp")`, and only then call `shim.call_tool(...)`.
   - denied calls must return a safe denial/error response and must not invoke the shim/MCP server.
   - no chat/ASI path is published by default.
9. Implement uAgent app:
   - constructs `uagents.Agent` from config.
   - constructs `HermesMCPClientShim` or fake/in-process MCP object.
   - includes the policy-aware direct protocol with `publish_manifest=True` for discoverability.
   - direct `ListTools`/`CallTool` path works without ASI key.
   - optional chat is disabled unless `chat.enable_chat: true` and `ASI1_API_KEY` is present.
10. If optional chat is implemented, gate it behind explicit config:
    - never publish chat protocol when disabled or no ASI key is present.
    - use redacted logging only.
    - configure timeouts and avoid blocking synchronous HTTP inside async handlers.
    - run the same sender/tool policy after model tool selection and before `shim.call_tool(...)`.
11. Implement local client example that sends `ListTools` and `CallTool` to the bridge.
12. Implement `hermes-fetch-ai doctor` and `probe-hermes`:
    - verify imports and package versions.
    - verify seed presence.
    - try `hermes mcp serve --help`.
    - attempt clean MCP initialize/list if configured.
    - record `mcp_serve` missing or MCP version mismatch as a precise blocker if seen.
13. Add docs and README with understated public story:
    "Hermes supplies the local agent/execution environment; Fetch supplies the public agent network; Hermes Fetch AI connects them."
14. Add contamination scan command/test for the required terms and document legitimate matches in `research/CONTAMINATION_AUDIT.md`.

Test strategy:

Run after each small task:

```bash
python -m pytest -q
```

Before final commit, run:

```bash
python -m pytest -q
python -m hermes_fetch_ai.cli doctor
python -m hermes_fetch_ai.cli demo local
```

If `ruff`/`mypy` are installed, also run:

```bash
python -m ruff check .
python -m mypy src/hermes_fetch_ai --ignore-missing-imports
```

Acceptance criteria:

- Local direct demo works with fake MCP server.
- Hermes probe precisely reports whether `hermes mcp serve` works or is blocked; real Hermes-backed demo is conditional on this probe succeeding.
- If Hermes MCP works, local client can list/call one safe Hermes-backed tool.
- Unknown sender is denied for non-public tools before shim/MCP invocation.
- Unknown sender `ListTools` returns only public-safe fake/status tools or an empty list.
- Allowed sender sees only explicitly allowed tools.
- Denied/side-effecting tools are absent from unauthorized `ListTools` responses.
- Denied calls produce audit records and no MCP invocation.
- No ASI key is needed for direct protocol.
- Agentverse/Mailbox config is documented but not required for CI.
- Chat protocol is not published unless explicitly enabled and ASI-key configured.
- Logs are redacted and structured; tests prove secret-like args/output are not emitted raw.
- `.env.example` contains names only.
- `research/CONTAMINATION_AUDIT.md` is updated after final scan.
- The later upstream Hermes PR plan remains separate and narrow.

Contamination/public-boundary scan before commit:

Search repo text for:
- MG
- Motion Granted
- citator
- client
- PACER
- Clay
- legal
- Tannerize
- private repo names
- credentials
- OpenClaw

For every match, either remove it or document why it is safe and necessary in `research/CONTAMINATION_AUDIT.md`. Do not include OpenClaw except as an out-of-scope term in audit/scope guardrails.

Commit guidance:

If the GitHub remote exists and push access works, commit safe files only with a conventional message. If the remote is still unresolved, record the exact blocker in `research/REPO_SETUP_STATUS.md` and continue local work. Never stage ignored logs, source/package dumps, or secrets.
