# Hardened Build Prompt
This document is the authoritative implementation prompt for the next autonomous coding session. It supersedes `research/BUILD_PROMPT.md` wherever they conflict. The reader is a coding agent that has read every research file under `research/`. The reader has NOT seen the original operator prompts; everything it needs is below.
Hand the prompt to the coding session verbatim, framed by your build orchestration instructions.
---
```text
You are continuing work in the Hermes Fetch AI repository.
Working directory:
C:\Users\ptann\OneDrive\Work\Hermes Fetch AI
Mission:
Build the standalone, private-first Hermes Fetch AI bridge as specified by `research/HARDENED_ARCHITECTURE_DECISION.md`. Ship a CI-grade local demo and a polished local Hermes-backed demo. Do not ship a public endpoint, payments, marketplace, wallet UX, chat protocol, or any side-effecting Hermes tool by default. Treat unknown remote agents as untrusted input. Treat uAgent sender identity as routing, not authorization.
This is a connection project, not a reinvention project. Fetch supplies identity/discovery/transport. Hermes supplies local execution. This repo supplies the thin policy-aware bridge.
Hard exclusions:
- Do NOT include OpenClaw architecture, references, examples, README language, implementation plans, or source material.
- Do NOT include legal-tech / domain-specific / private workflow content.
- Do NOT build payments, billing, marketplace pricing, per-skill commercial manifests, or wallet UX beyond seed/address identity handling.
- Do NOT publish `MCPServerAdapter.protocols`. Import only message-model symbols and `mcp_protocol_spec` from `uagents_adapter.mcp.protocol`.
- Do NOT publish the adapter chat protocol. Chat is out of v1.
- Do NOT expose any Hermes tool to unknown senders other than `skills_list` by default.
- Do NOT commit `.env`, secrets, caches, logs, virtualenvs, `node_modules`, credentials, package dumps, or unrelated project files.
- Do NOT use destructive git operations, force push, --no-verify, or amend published commits.
Evidence to consult (already in the repo):
- `research/HARDENING_AUDIT.md`
- `research/HARDENED_ARCHITECTURE_DECISION.md` (this is the authoritative architecture)
- `research/HERMES_MCP_SURFACE.md`
- `research/FETCH_UAGENTS_SURFACE.md`
- `research/MCP_ADAPTER_INVESTIGATION.md`
- `research/MCP_ADAPTER_SPIKE_PLAN.md`
- `research/E2E_DEMO_PLAN.md`
- `research/SECURITY_MODEL.md`
- `research/V1_SCOPE.md`
- `research/PUBLIC_POSITIONING.md`
- `research/REPO_IMPLEMENTATION_PLAN.md`
- `research/UPSTREAM_PR_PLAN.md`
- `research/OPEN_QUESTIONS.md`
- `research/RESEARCH_INDEX.md`
- `research/CONTAMINATION_AUDIT.md`
Vendored evidence under `research/repos/` and `research/pkgs/` is git-ignored and present for source verification. Do NOT commit it.
==========================================================================
1. PACKAGE LAYOUT (file tree)
==========================================================================
Create this layout. Every file listed exists in the final commit; nothing else under src/ or tests/ unless this prompt says so.
pyproject.toml
README.md
LICENSE                                 (Apache-2.0; mirror upstream uAgents adapter license)
.gitignore                              (already exists; do not weaken)
.env.example                            (placeholders only; no real values)
src/hermes_fetch_ai/__init__.py
src/hermes_fetch_ai/__main__.py         (delegates to cli:main)
src/hermes_fetch_ai/cli.py
src/hermes_fetch_ai/config.py
src/hermes_fetch_ai/logging.py
src/hermes_fetch_ai/audit.py
src/hermes_fetch_ai/policy.py
src/hermes_fetch_ai/arg_validator.py
src/hermes_fetch_ai/result_normalizer.py
src/hermes_fetch_ai/mcp_shim.py
src/hermes_fetch_ai/direct_protocol.py
src/hermes_fetch_ai/uagent_app.py
src/hermes_fetch_ai/registration_policies.py
src/hermes_fetch_ai/hermes_probe.py
src/hermes_fetch_ai/version_pins.py
src/hermes_fetch_ai/_redaction.py
examples/local-direct.yaml
examples/hermes-local.yaml
examples/agentverse-mailbox.yaml
examples/fake_mcp_server.py
examples/local_client.py
examples/README.md
tests/conftest.py
tests/test_config.py
tests/test_policy.py
tests/test_arg_validator.py
tests/test_result_normalizer.py
tests/test_mcp_shim_fake_server.py
tests/test_direct_protocol_policy.py
tests/test_uagent_direct_protocol.py
tests/test_security_defaults.py
tests/test_redaction.py
tests/test_contamination.py
tests/fakes/fake_mcp_subprocess.py      (helper invoked by test_mcp_shim_fake_server.py)
docs/architecture.md
docs/security.md
docs/demo.md                            (includes a "Windows" section)
docs/troubleshooting.md
docs/upstream-hermes-pr.md
==========================================================================
2. DEPENDENCIES (pyproject.toml)
==========================================================================
[project]
name = "hermes-fetch-ai"
version = "0.1.0"
description = "Thin policy-aware bridge between Hermes Agent and Fetch.ai uAgents."
license = { text = "Apache-2.0" }
requires-python = ">=3.11,<3.13"
dependencies = [
  "uagents==0.24.2",
  "uagents-core==0.4.4",
  "uagents-adapter[mcp]==0.6.2",
  "mcp>=1.27.1,<2.0",
  "pydantic>=2.8,<3",
  "PyYAML>=6,<7",
  "python-dotenv>=1.0,<2",
  "jsonschema>=4.20,<5",
  "httpx>=0.25,<1",
]
[project.optional-dependencies]
dev = [
  "pytest>=8,<9",
  "pytest-asyncio>=0.23,<1",
  "anyio>=4,<5",
  "ruff>=0.5",
  "mypy>=1.10",
  "types-PyYAML",
]
[project.scripts]
hermes-fetch-ai = "hermes_fetch_ai.cli:main"
[tool.pytest.ini_options]
asyncio_mode = "auto"
[tool.ruff]
line-length = 100
target-version = "py311"
`version_pins.py` re-exports these as constants so `doctor` can verify the installed versions match the pin.
Do NOT add unpinned upper-bound-free dependencies. Do NOT pull `openai` directly (it arrives transitively via uagents-adapter; that is acceptable; the bridge code must not import openai). Do NOT pull `requests` directly (use `httpx` if needed).
==========================================================================
3. MODULE RESPONSIBILITIES
==========================================================================
config.py
- Loads `--config <path>` YAML, merged with environment variables.
- Required env: `UAGENT_SEED` unless `agent.dev_random_seed: true` (which derives a random seed at startup, prints the address, never persists).
- Config schema (validate with pydantic; document version=1):
    version: 1
    agent:
      name: "hermes-fetch-ai"
      port: 8000
      network: "testnet"             # default testnet; mainnet only on explicit opt-in
      mode: "endpoint"               # endpoint | mailbox | proxy
      endpoint: ["http://127.0.0.1:8000/submit"]
      dev_random_seed: false
      publish_manifest: false        # CI default false; demo turns true
      enable_agent_inspector: false  # CI default false; demo may enable
      description: "..."
      readme_path: null
    hermes_mcp:
      mode: "fake"                   # fake | in_process_hermes_tools | stdio | sse | http
      command: null                  # stdio mode only
      args: []                       # stdio mode only
      env_passthrough: ["PATH", "HOME", "USERPROFILE", "HERMES_HOME", "HERMES_QUIET", "HERMES_REDACT_SECRETS"]
      url: null                      # sse/http modes only
      headers: {}                    # sse/http modes only
      connect_timeout_seconds: 30
      call_timeout_seconds: 60
    policy:
      public_tools: []               # tools visible/callable by ANY signed sender
      allowed_senders: {}            # mapping {sender_address: [tool names]}
      denied_tools: []               # absolute denylist; overrides allowlists
      max_args_bytes: 65536
      max_output_bytes: 65536
      max_calls_per_minute_per_sender: 30
    logging:
      level: "INFO"
      json: true
      audit_path: null               # null -> platform default (see below)
      redaction: true
    chat:
      enable_chat: false             # MUST stay false for v1; reject true with NotImplementedError
- Platform default audit path:
    POSIX:  ${XDG_STATE_HOME:-~/.local/state}/hermes-fetch-ai/audit.jsonl
    Windows: %LOCALAPPDATA%\\HermesFetchAI\\audit.jsonl
- Hard fail on:
    - missing UAGENT_SEED when dev_random_seed is false
    - chat.enable_chat: true (v1 invariant)
    - hermes_mcp.mode == "stdio" with no command
    - any secret-shaped value embedded in YAML
logging.py
- Wraps stdlib logging. Adds a redacting formatter that masks token-like strings (Bearer, jwt-like, hex>=32, sk-/pk- prefixes). Reuse the regex set from `_redaction.py`.
- Provides `get_logger(name)`.
_redaction.py
- Pure regex helpers: `redact_text(s) -> str`, `redact_dict(d) -> dict` (deep copy, applied to values).
- Patterns include: `(?i)bearer\s+[A-Za-z0-9._\-]{8,}`, `(?:sk|pk)-[A-Za-z0-9]{16,}`, `[A-Fa-f0-9]{32,}` (hex secrets/seeds), JWT-shaped, base64 secrets >= 24 chars, `seed[\"']?\s*[:=]\s*[\"'][^\"']+[\"']`.
- Sender uAgent addresses are NOT redacted but are TRUNCATED to `agent1qvx…last8` in logs and audit.
audit.py
- JSONL writer (append, rotate at 25 MiB, keep 5 files).
- Event schema:
    { ts, trace_id, sender_short, protocol, msg_type, tool, decision,
      reason, duration_ms, args_bytes, output_bytes, truncated,
      error_class, mode }
- Never writes raw args, prompts, tool outputs, seeds, tokens, API keys.
policy.py
- Pure functions over typed objects. No I/O.
- `visible_tools(sender: str, tools: list[mcp.types.Tool], cfg: PolicyConfig) -> list[mcp.types.Tool]`:
    - if denied_tools includes tool.name -> drop
    - if sender in allowed_senders and tool.name in allowed_senders[sender] -> keep
    - elif tool.name in public_tools -> keep
    - else drop
- `authorize(sender, tool, args, protocol, cfg) -> AuthorizationDecision`:
    - returns Decision(allow: bool, reason: str)
    - default deny
    - denied_tools always wins
    - rate-limit check per sender (token bucket; in-process state)
- `default_safe_public_tools() -> set[str]`: returns {"skills_list"} -- only this Hermes tool is approved for public exposure by default; any other tool requires explicit operator opt-in.
arg_validator.py
- `validate_args(tool: mcp.types.Tool, args: dict) -> None` -> raises `InvalidArgsError(reason)` on:
    - jsonschema validation failure against `tool.inputSchema`
    - any string field that looks like a URL pointing to RFC1918 / link-local / loopback / 0.0.0.0 ranges (default; override per tool)
    - any string field containing shell metacharacters when the tool's schema says it's not a shell command
- Default-safe URL host blocklist: 127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16, ::1, fc00::/7, fe80::/10, 0.0.0.0/8.
result_normalizer.py
- @dataclass NormalizedToolResult: text: str, structured: dict | None, is_error: bool, truncated: bool, output_bytes: int.
- `from_call_tool_result(result: mcp.types.CallToolResult, max_bytes: int) -> NormalizedToolResult`:
    - concatenates text content blocks
    - captures structuredContent if present
    - drops image/audio/resource blocks to a short placeholder like "[binary: image/png, 12 KiB]"
    - truncates at max_bytes with explicit "[…truncated]" marker
    - is_error mirrors result.isError
mcp_shim.py
- class `HermesMCPClientShim`:
    - constructor takes a `HermesMcpConfig` (the subsection of validated config).
    - mode "fake": uses an in-memory FastMCP server in the same process. Calls `_build_fake_server(...)` defined in `examples/fake_mcp_server.py` or test fixture.
    - mode "in_process_hermes_tools": lazy-imports `agent.transports.hermes_tools_mcp_server._build_server` and uses it directly.
    - mode "stdio": uses `mcp.client.stdio.stdio_client` + `mcp.ClientSession` against the configured command/args/env-filtered subprocess. Subprocess stderr is redirected to a tempfile-backed handle; the path is logged once and never read into bridge logs.
    - mode "sse" / "http": uses `mcp.client.sse.sse_client` / `mcp.client.streamable_http.streamablehttp_client`.
    - Owns a dedicated background event loop in a daemon thread for stdio mode (Hermes-style pattern; see `tools/mcp_tool.py:60-65`). For in-process / fake mode, no background loop is needed because the server runs on the same loop.
    - Methods:
        - `async start(self) -> None`
        - `async aclose(self) -> None`
        - `async list_tools(self) -> list[mcp.types.Tool]`
        - `async call_tool(self, name: str, args: dict | None) -> NormalizedToolResult`
        - async context manager `__aenter__` / `__aexit__`
    - Per-call timeout via `mcp.ClientSession.call_tool(..., read_timeout_seconds=timedelta(seconds=cfg.call_timeout_seconds))`.
    - Reconnect on broken-pipe: bounded retries (max 2) with exponential backoff (1 s, 4 s).
    - NEVER pass the shim to `MCPServerAdapter`.
direct_protocol.py
- Imports `mcp_protocol_spec`, `ListTools`, `ListToolsResponse`, `CallTool`, `CallToolResponse` from `uagents_adapter.mcp.protocol` (wire compatibility).
- Defines `build_protocol(shim, policy_cfg, audit, logger) -> uagents.Protocol`:
    - `proto = Protocol(spec=mcp_protocol_spec, role="server")`
    - `@proto.on_message(model=ListTools)` handler:
        - sender size check on incoming envelope (read from ctx if available; else accept and rely on uAgents server cap)
        - tools = await shim.list_tools()
        - visible = policy.visible_tools(sender, tools, policy_cfg)
        - audit allow with len(visible)/len(tools)
        - return ListToolsResponse(tools=[serialize(t) for t in visible], error=None)
    - `@proto.on_message(model=CallTool)` handler:
        - reject if args > max_args_bytes (json encoded)
        - decision = policy.authorize(sender, msg.tool, msg.args, "direct_mcp", policy_cfg)
        - if not decision.allow: audit deny; return CallToolResponse(result=None, error=decision.reason)
        - tools = await shim.list_tools(); find tool; if not found: deny
        - arg_validator.validate_args(tool, msg.args)
        - result = await shim.call_tool(msg.tool, msg.args)
        - serialized = result.text (or json.dumps(result.structured) if structured-only)
        - audit allow with output_bytes, truncated
        - return CallToolResponse(result=serialized, error=result.is_error and "tool reported error" or None)
- Both handlers MUST be signed-only handlers (i.e. `proto.on_message`, which uses signed message handlers). Do NOT use `on_query` here.
uagent_app.py
- `async def run_bridge(cfg: BridgeConfig) -> None`:
    - constructs registration_policy = NoopRegistrationPolicy() if cfg.agent.publish_manifest is False else None (default policy used in demos)
    - constructs `Agent(name=cfg.agent.name, port=cfg.agent.port, seed=seed, endpoint=endpoint_or_None, mailbox=cfg.agent.mode == "mailbox", proxy=cfg.agent.mode == "proxy", network=cfg.agent.network, registration_policy=registration_policy, enable_agent_inspector=cfg.agent.enable_agent_inspector, readme_path=cfg.agent.readme_path, description=cfg.agent.description)`
    - constructs shim per cfg.hermes_mcp.mode
    - starts shim
    - protocol = build_protocol(shim, cfg.policy, audit, logger)
    - `agent.include(protocol, publish_manifest=cfg.agent.publish_manifest)`
    - assert chat is not enabled: if cfg.chat.enable_chat: raise NotImplementedError("chat is out of v1 scope")
    - await agent.run_async() (use the async entrypoint)
    - on shutdown: await shim.aclose()
registration_policies.py
- class NoopRegistrationPolicy(AgentRegistrationPolicy): `async def register(...) -> None: return` (no Almanac calls, no network).
- Documented for use in CI and offline demos.
hermes_probe.py
- async function `probe() -> ProbeReport` checking:
    1. `hermes-agent` importable (returns version).
    2. `hermes-agent[mcp]` available (`from mcp.client.stdio import stdio_client`).
    3. `agent.transports.hermes_tools_mcp_server._build_server` importable.
    4. `hermes` console script on PATH.
    5. `hermes mcp serve --help` returncode (warn on `ModuleNotFoundError: mcp_serve`).
- Prints actionable hints. Does NOT print env values or secrets.
cli.py
- subcommands:
    - `doctor`: env, python version (must be 3.11.x or 3.12.x), pinned versions installed, seed present, audit path writable, config sample valid. Return non-zero on any failure.
    - `probe-hermes`: runs hermes_probe.probe(), prints structured report.
    - `serve --config PATH`: load config, asyncio.run(run_bridge(cfg)).
    - `demo local`: equivalent of `serve --config examples/local-direct.yaml`; bundles two agents (bridge + sample client) in a single process and prints the round-trip.
    - `demo mailbox`: same as `serve --config examples/agentverse-mailbox.yaml`, with extra preflight (refuses if UAGENT_SEED missing).
- All commands return integer exit codes; never raise to the user without a friendly message.
audit.py / logging.py / _redaction.py — see above.
==========================================================================
4. EXAMPLES
==========================================================================
examples/local-direct.yaml:
    version: 1
    agent:
      name: "hermes-fetch-ai-demo"
      port: 8000
      network: "testnet"
      mode: "endpoint"
      endpoint: ["http://127.0.0.1:8000/submit"]
      dev_random_seed: true
      publish_manifest: false
      enable_agent_inspector: false
    hermes_mcp:
      mode: "fake"
    policy:
      public_tools: ["echo"]
      max_args_bytes: 8192
      max_output_bytes: 8192
      max_calls_per_minute_per_sender: 30
    logging:
      level: "INFO"
      json: true
      redaction: true
    chat:
      enable_chat: false
examples/hermes-local.yaml:
    Same as local-direct, but hermes_mcp.mode: "in_process_hermes_tools" and policy.public_tools: ["skills_list"] and policy.denied_tools includes every other entry from `agent.transports.hermes_tools_mcp_server.EXPOSED_TOOLS`.
examples/agentverse-mailbox.yaml:
    Same as hermes-local, but agent.mode: "mailbox", agent.publish_manifest: true, agent.enable_agent_inspector: true, dev_random_seed: false (requires real UAGENT_SEED).
examples/fake_mcp_server.py:
- Defines `_build_fake_server() -> FastMCP`:
    from mcp.server.fastmcp import FastMCP
    s = FastMCP("hermes-fetch-ai-fake")
    @s.tool() def echo(text: str) -> str: return text
    @s.tool() def add(a: int, b: int) -> int: return a + b
    return s
- Used both by tests and the `local-direct.yaml` example.
examples/local_client.py:
- Starts a client uAgent that sends `ListTools` followed by `CallTool(echo, {"text": "hello"})` to the bridge address. Designed to run in the SAME process for `demo local`.
==========================================================================
5. TESTS
==========================================================================
All tests must be runnable with `python -m pytest -q`, no hosted dependencies, no Agentverse, no ASI key, no Hermes install. Mark Hermes-backed tests with `@pytest.mark.skipif("not _hermes_available")` and gate on env `HERMES_FETCH_AI_E2E_HERMES=1`.
tests/conftest.py:
- Fixture `event_loop` (anyio if needed).
- Fixture `bridge_seed` (deterministic test seed; NOT used at runtime, only in tests).
- Fixture `bridge_cfg` returning a valid BridgeConfig for fake mode.
- Fixture `monkeypatch_agentverse_unreachable`: sets env `AGENTVERSE_URL=http://127.0.0.1:1` so any accidental network call fails fast.
- Fixture `bridge_and_client`: creates two `uagents.Agent` instances with `NoopRegistrationPolicy`, `enable_agent_inspector=False`, `publish_manifest=False`, `network="testnet"`, includes the bridge's direct protocol on the bridge agent. Returns both addresses + a `send_and_wait(msg, expect=Response)` helper using `dispatcher` directly (no HTTP).
- Cleanup: closes shims, cancels agent tasks.
Required test cases (names are illustrative; the goal is full coverage of the listed behaviors):
test_config.py
- missing UAGENT_SEED rejected unless dev_random_seed=true
- chat.enable_chat=true rejected with NotImplementedError
- audit_path defaults per platform
- mode stdio requires command
- secret-shaped values in yaml rejected
test_policy.py
- empty policy denies everything
- denylist beats allowlist
- visible_tools filters per sender
- rate limit blocks 31st call within 60 seconds
- public_tools default safe set = {"skills_list"} (sanity check string)
test_arg_validator.py
- jsonschema violation raises
- URL field pointing to 127.0.0.1 rejected
- URL field pointing to RFC1918 rejected
- URL field pointing to 0.0.0.0 rejected
- Shell metacharacter in non-shell field rejected (config flag to opt out)
test_result_normalizer.py
- text content concatenation
- structured content captured
- image content replaced by placeholder
- isError flag mirrored
- truncation at max_bytes with marker
test_mcp_shim_fake_server.py
- list_tools returns FakeMCP tools (fake mode)
- call_tool round trips
- stdio mode launches subprocess (uses tests/fakes/fake_mcp_subprocess.py)
- subprocess env is filtered to allowlist
- subprocess stderr does not contaminate bridge stdout/stderr
- per-call timeout returns a structured timeout error
- bounded reconnect on broken pipe
test_direct_protocol_policy.py
- unknown sender ListTools returns only public_tools (or empty if default)
- allowlisted sender ListTools returns only their allowed tools
- denied tool CallTool returns CallToolResponse(error=...) WITHOUT invoking shim (assert via spy)
- oversize args denied before shim
- arg validator failure produces denial without shim call
test_uagent_direct_protocol.py
- two Agents in one process: client ListTools succeeds via dispatcher
- two Agents in one process: client CallTool("echo") returns "hello"
- bridge protocol uses signed handlers only (assert no unsigned handler is registered for our schema digests)
- `agent.protocols` does NOT contain `MCPServerAdapter`'s protocols (spec digest comparison)
- `agent.protocols` contains exactly ONE protocol with `mcp_protocol_spec` name
test_security_defaults.py
- chat protocol is absent when chat.enable_chat=false (assert no protocol with name "AgentChatProtocol")
- doctor banner does not include the seed (capture stdout, assert seed substring absent)
- audit log does not include sender's full address (only truncated form)
- audit log does not include raw args bytes or raw output bytes
- oversize CallTool args rejected before shim call
- publish_manifest defaults to false in CI configs
test_redaction.py
- Bearer tokens redacted
- sk-/pk- API key shapes redacted
- hex secrets >= 32 chars redacted
- seed values in JSON-like strings redacted
- uAgent addresses truncated to agent1qvx…last8
test_contamination.py
- For each file in src/, docs/, examples/, README.md, .env.example, pyproject.toml: assert it does NOT contain any of:
    MG, Motion Granted, citator, PACER, Clay, Tannerize, OpenClaw,
    private repo names, the word "legal" in non-license context.
- Files explicitly carved out: research/, the operator prompts at repo root, this hardened build prompt, the hardening audit, the contamination audit.
==========================================================================
6. CLI BEHAVIOR (exact)
==========================================================================
hermes-fetch-ai doctor
- prints a structured table:
    Python version: 3.11.x ok / 3.13.x WARN (deprecated event loop policy)
    Installed: uagents==0.24.2 ok, mcp==1.27.x ok, ...
    Seed: configured / not configured / random (dev)
    Audit path: <path>  writable: ok|fail
    Config sample (local-direct.yaml): valid|invalid: <reason>
- exits 0 on success, 2 on missing/invalid env/seed, 3 on pin mismatch, 4 on audit-path failure.
hermes-fetch-ai probe-hermes
- prints, in order:
    hermes import: ok|missing  (version ...)
    hermes[mcp] import: ok|missing
    hermes_tools_mcp_server._build_server: ok|missing  (tools available: N)
    hermes console script: <path>|not on PATH
    hermes mcp serve --help: ok|ModuleNotFoundError: mcp_serve|other (...)
- exits 0 if at least one Hermes-backed path is usable; 1 otherwise.
hermes-fetch-ai serve --config PATH
- starts the bridge.
- on SIGINT, performs `await shim.aclose()` then `agent.shutdown()`.
hermes-fetch-ai demo local
- inline subcommand. Calls `serve` with `examples/local-direct.yaml`, then in the same process starts the `examples/local_client.py` flow. Prints the round trip and exits 0 on success.
hermes-fetch-ai demo mailbox
- requires UAGENT_SEED. Refuses to start if missing.
- otherwise behaves like `serve --config examples/agentverse-mailbox.yaml`.
==========================================================================
7. CONFIG SCHEMA (canonical)
==========================================================================
See section 3 for the schema. Validate with pydantic v2. Reject unknown fields. Reject `chat.enable_chat: true` in v1. Pin schema `version: 1`.
==========================================================================
8. POLICY MODEL
==========================================================================
Default deny. Three layers:
1. denied_tools (absolute denylist; overrides everything)
2. allowed_senders[sender] (explicit per-sender allowlist; ListTools and CallTool both honor it)
3. public_tools (visible/callable by any signed sender)
`visible_tools(sender, tools, cfg)`:
- For each tool t in tools:
  - if t.name in cfg.denied_tools: drop
  - elif sender in cfg.allowed_senders and t.name in cfg.allowed_senders[sender]: keep
  - elif t.name in cfg.public_tools: keep
  - else: drop
`authorize(sender, tool, args, protocol, cfg)`:
- if rate limit exceeded: deny "rate limit"
- if tool in cfg.denied_tools: deny "denied tool"
- if sender in cfg.allowed_senders and tool in cfg.allowed_senders[sender]: allow
- if tool in cfg.public_tools: allow
- else: deny "tool not allowed for sender"
Default `policy.public_tools` for the Hermes-backed example: ["skills_list"]. For the fake example: ["echo"].
==========================================================================
9. AUDIT LOGGING MODEL
==========================================================================
JSONL append; rotate at 25 MiB; keep 5 files.
Required fields:
- ts (ISO 8601 UTC)
- trace_id (uuid4)
- sender_short (e.g. "agent1qvx…7zk8a")
- protocol ("direct_mcp")
- msg_type ("list_tools" | "call_tool")
- tool (string | null)
- decision ("allow" | "deny")
- reason (string)
- duration_ms (int)
- args_bytes (int | null)
- output_bytes (int | null)
- truncated (bool | null)
- error_class (string | null)
- mode (hermes_mcp.mode value)
Never write raw args, raw output, seeds, tokens, API keys.
==========================================================================
10. MCP SHIM BEHAVIOR (exact)
==========================================================================
- Modes: fake (in-process FastMCP), in_process_hermes_tools (lazy imports `_build_server`), stdio (default for production), sse, http.
- For stdio mode:
  - StdioServerParameters(command=cfg.command, args=cfg.args, env=filtered_env, cwd=None).
  - filtered_env = { k: os.environ[k] for k in cfg.env_passthrough if k in os.environ }.
  - subprocess stderr redirected to a tempfile in the audit dir; path logged once at INFO; never read into the bridge log stream.
  - dedicated background loop on a daemon thread (Hermes pattern).
  - reconnect: max 2 attempts, exponential backoff 1s, 4s. Each reconnect uses a fresh ClientSession.
- list_tools:
  - await session.list_tools(); return result.tools.
- call_tool:
  - read_timeout = timedelta(seconds=cfg.call_timeout_seconds).
  - res = await session.call_tool(name, args or {}, read_timeout_seconds=read_timeout).
  - return result_normalizer.from_call_tool_result(res, max_bytes=cfg.max_output_bytes_used_by_normalizer).
- Never pass `self` to `MCPServerAdapter(...)`.
==========================================================================
11. uAGENT PROTOCOL BEHAVIOR (exact)
==========================================================================
- One protocol: `Protocol(spec=mcp_protocol_spec, role="server")`.
- Two signed message handlers: ListTools, CallTool.
- ListTools handler:
  - tools = await shim.list_tools()
  - filtered = policy.visible_tools(sender, tools, cfg.policy)
  - serialized = [{"name": t.name, "description": t.description or "", "inputSchema": t.inputSchema or {"type":"object","properties":{}}} for t in filtered]
  - audit("list_tools", sender, decision="allow", reason="visible=%d/%d" % (len(filtered), len(tools)))
  - await ctx.send(sender, ListToolsResponse(tools=serialized, error=None))
- CallTool handler:
  - json_bytes = len(json.dumps(msg.args or {}, ensure_ascii=False).encode("utf-8"))
  - if json_bytes > cfg.policy.max_args_bytes: deny, send error response
  - decision = policy.authorize(sender, msg.tool, msg.args or {}, "direct_mcp", cfg.policy)
  - if not decision.allow: deny, send error response, do NOT call shim
  - tools = await shim.list_tools(); tool = first t where t.name == msg.tool; if not tool: deny "unknown tool"
  - arg_validator.validate_args(tool, msg.args or {})
  - try:
      result = await shim.call_tool(msg.tool, msg.args or {})
    except Exception as exc:
      audit deny "shim error: %s" % exc.__class__.__name__
      send error response
      return
  - send CallToolResponse(result=result.text or json.dumps(result.structured), error=("tool reported error" if result.is_error else None))
  - audit allow with output_bytes, truncated, duration_ms
==========================================================================
12. DEMO ACCEPTANCE CRITERIA
==========================================================================
Local CI demo (no hosted deps):
- `python -m pytest -q` passes on Windows and on POSIX.
- `python -m hermes_fetch_ai.cli doctor` exits 0 in a clean venv.
- `python -m hermes_fetch_ai.cli demo local` prints:
    - bridge address
    - "ListTools -> 1 tool visible: echo"
    - "CallTool(echo, {text: hello}) -> hello"
    - "audit: 2 events written to <path>"
- No HTTP traffic on the loopback interface (verify by running on a host with no internet access).
Hermes-backed local demo (manual; not in CI):
- `python -m hermes_fetch_ai.cli probe-hermes` reports `_build_server: ok`.
- `python -m hermes_fetch_ai.cli serve --config examples/hermes-local.yaml` starts.
- Manual client: `python examples/local_client.py --bridge <addr> --tool skills_list --args '{}'` returns a non-empty list of skills.
- All other Hermes tools attempted by the client return a structured deny.
Mailbox demo (manual; CEO demo only):
- `python -m hermes_fetch_ai.cli demo mailbox` prints the agent address and inspector URL.
- Operator links the mailbox in Agentverse.
- A remote uAgent sends ListTools; response shows only the configured public tool(s).
==========================================================================
13. SECURITY ACCEPTANCE CRITERIA
==========================================================================
All of the following MUST be true (enforced by tests in `test_security_defaults.py`):
- `MCPServerAdapter.protocols` is not added to the bridge agent.
- No chat protocol is added unless `chat.enable_chat: true` (and that branch raises NotImplementedError in v1).
- Default `public_tools` for the Hermes-backed example is exactly `["skills_list"]`.
- Side-effecting Hermes tools (web search, browser, image gen, TTS, kanban) appear in `denied_tools` in the Hermes example.
- Doctor never prints the seed value.
- Audit log never contains raw args/output/tokens/seeds.
- Sender addresses appear in truncated form in logs and audit.
- `CallTool.args` above `max_args_bytes` is denied without shim invocation.
- Denied calls do not invoke the shim.
- Unknown sender ListTools returns only `public_tools` or empty.
- Stdio subprocess env is filtered to allowlist.
- Stdio subprocess stderr does not contaminate bridge stdout/stderr.
- Per-call timeout returns a structured timeout error.
==========================================================================
14. CONTAMINATION SCAN
==========================================================================
`tests/test_contamination.py` enforces:
- Forbidden terms in src/, docs/, examples/, README.md, .env.example, pyproject.toml, LICENSE:
    MG, "Motion Granted", citator, PACER, Clay, Tannerize, OpenClaw, the word "legal" outside the LICENSE text.
- Allowed locations (skipped by the test): research/, the two operator prompt files at repo root (`HERMES_RESEARCH_PROMPT.md`, `AFTER_REPO_SETUP_PROMPT.md`), `research/HARDENED_BUILD_PROMPT.md`, `research/HARDENING_AUDIT.md`, `research/CONTAMINATION_AUDIT.md`.
Also re-run a manual scan as part of `cli doctor` (`hermes-fetch-ai doctor --contamination-scan`), which exits non-zero if anything new appears in code or docs.
==========================================================================
15. DOCS TO WRITE
==========================================================================
docs/architecture.md
- Summary: connection project, not reinvention.
- Why the bridge owns its protocol (vs `MCPServerAdapter.protocols`).
- Why chat is off by default.
- The exact message flow diagram.
- The three trust boundaries with credential placements.
docs/security.md
- Threat model.
- Default deny rationale.
- Policy layers.
- Stdio subprocess hardening (env filter, stderr redirect).
- Why uAgent sender identity is routing, not authorization.
docs/demo.md
- Local CI demo commands.
- Hermes-backed local demo commands.
- Mailbox demo (manual).
- Windows section (PowerShell activation, `py -3.12` resolution, `where hermes`).
docs/troubleshooting.md
- "ModuleNotFoundError: mcp_serve" -> use mode `in_process_hermes_tools` or `fake`.
- "Address already in use" -> choose a different port.
- "Almanac API failed" warnings -> use `NoopRegistrationPolicy` in CI or `publish_manifest: false`.
- "Tool not allowed for sender" -> check policy.allowed_senders / public_tools.
- "Schema validation failed" -> check the tool's inputSchema in `list_tools` response.
docs/upstream-hermes-pr.md
- Recommend Option B: a Hermes-native `hermes uagents serve` command/plugin.
- Why Option A (gateway platform adapter) is NOT recommended: `BasePlatformAdapter` is designed for chat platforms (Telegram/Discord/WhatsApp/Weixin) with sessions/threads/typing/drafts/voice mode, not RPC.
- What ports: shim, normalizer, policy primitives, redaction patterns, audit schema, tests.
- What does NOT port: standalone CLI wrapper, example YAML, demo runner, research files, experimental spike code, vendored evidence caches.
- Optional dependency strategy: `hermes-agent[uagents]` extra carrying uagents, uagents-core, uagents-adapter[mcp], mcp.
- Hooks: any Hermes-native upstream must run Hermes' existing `pre_tool_call` and `post_tool_call` hooks for tools dispatched by external agents.
- Attribution: cite the imported message-model symbols and protocol spec from `uagents_adapter.mcp.protocol` (Apache-2.0).
==========================================================================
16. FINAL GIT / PR EXPECTATIONS
==========================================================================
- Use the standing `main` branch. Do not create separate branches without explicit user direction.
- Make small, focused commits in build order (see "Build order" below).
- Conventional commit prefixes: `feat:`, `chore:`, `test:`, `docs:`, `fix:`.
- Never run `git push`, `git rebase -i`, `--amend` on a pushed commit, or `--no-verify`.
- Never stage research/repos/, research/pkgs/, research/public/, logs/, .venv/, .env, *.log.
- After the final feature commit, run:
    - python -m pytest -q
    - python -m hermes_fetch_ai.cli doctor
    - python -m hermes_fetch_ai.cli demo local
    - ruff check . (if installed)
    - mypy src/hermes_fetch_ai --ignore-missing-imports (if installed)
- If any of these fails, fix and add a new commit. Do NOT amend.
- Do NOT open a GitHub PR — the remote does not exist (see research/REPO_SETUP_STATUS.md). Print the final commit SHA and a one-line PR-ready description and stop.
==========================================================================
17. BUILD ORDER (incremental, test-after-each)
==========================================================================
1. pyproject.toml + version_pins.py + .env.example + minimal README.md placeholder.
2. _redaction.py + tests/test_redaction.py.
3. logging.py + audit.py (with tempdir tests in conftest).
4. config.py + tests/test_config.py.
5. policy.py + tests/test_policy.py.
6. arg_validator.py + tests/test_arg_validator.py.
7. result_normalizer.py + tests/test_result_normalizer.py.
8. examples/fake_mcp_server.py + tests/fakes/fake_mcp_subprocess.py.
9. mcp_shim.py (fake + in_process_hermes_tools + stdio) + tests/test_mcp_shim_fake_server.py.
10. registration_policies.py.
11. direct_protocol.py + tests/test_direct_protocol_policy.py.
12. uagent_app.py + tests/test_uagent_direct_protocol.py.
13. hermes_probe.py + cli.py + tests/test_security_defaults.py.
14. examples/local-direct.yaml, hermes-local.yaml, agentverse-mailbox.yaml, local_client.py, examples/README.md.
15. docs/* (architecture, security, demo, troubleshooting, upstream-hermes-pr).
16. tests/test_contamination.py.
17. Final README.md polish (use research/PUBLIC_POSITIONING.md verbatim where possible).
18. Final doctor + demo run; commit.
==========================================================================
18. STOP/GO CRITERIA
==========================================================================
GO when (and only when) all of these are true:
- `python -m pytest -q` passes.
- `python -m hermes_fetch_ai.cli doctor` exits 0.
- `python -m hermes_fetch_ai.cli demo local` prints the expected three lines.
- `tests/test_contamination.py` passes.
- `agent.protocols` for the bridge contains exactly the bridge-owned MCP protocol (no chat, no `MCPServerAdapter.*`).
STOP and ask the user if:
- Any forbidden term sneaks into code or docs.
- A new external dependency would be added.
- A test would need to be marked xfail to ship.
- A network call is required to complete CI.
- The Hermes packaging blocker (`mcp_serve.py`) appears to have been fixed upstream — report and ask for new pins.
DO NOT proceed if any STOP condition holds.
==========================================================================
END OF HARDENED BUILD PROMPT
==========================================================================
```
