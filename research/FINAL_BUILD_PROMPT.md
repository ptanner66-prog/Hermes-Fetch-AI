# Final Build Prompt

This supersedes `research/HARDENED_BUILD_PROMPT.md`. Hand this file to the autonomous coding agent verbatim. It is intended to be directly executable over a multi-day implementation session.

```text
You are implementing Hermes Fetch AI in the repository:
C:\Users\ptann\OneDrive\Work\Hermes Fetch AI

Mission
Build the thinnest policy-aware bridge between Hermes Agent and Fetch.ai uAgents.

Core philosophy
This is a connection project, not a reinvention project. Fetch supplies identity, addressing, discovery, Agentverse/Almanac rails, mailbox/proxy/endpoint modes, signed envelopes, dispatcher, and uAgent protocols. Hermes supplies local intelligence, tools, MCP, configuration, redaction, and execution boundaries. This repo supplies policy, normalization, audit, config, tests, docs, and demos.

Authoritative docs
Read these first:
- research/FINAL_ARCHITECTURE_DECISION.md
- research/EXTREME_HARDENING_AUDIT.md
- research/OPEN_QUESTIONS.md
- research/CONTAMINATION_AUDIT.md
- research/SECURITY_MODEL.md
- research/HERMES_MCP_SURFACE.md
- research/FETCH_UAGENTS_SURFACE.md
- research/UPSTREAM_PR_PLAN.md

Hard exclusions
- Do not include OpenClaw architecture, docs, examples, or source material.
- Do not include legal-tech/private/domain-specific content.
- Do not build payments, billing, marketplace, wallet UX beyond seed/address identity, or per-skill commercial manifests.
- Do not publish or depend on MCPServerAdapter.protocols as the v1 security boundary.
- Do not enable or publish chat protocol in v1.
- Do not invent a new agent framework.
- Do not expose side-effecting Hermes tools by default.
- Do not print, inspect, or write secrets.
- Do not commit .env, logs, caches, virtualenvs, vendored research repos/packages, package dumps, keys, certs, or credentials.

Git rules
- Work on main.
- origin/main exists: https://github.com/ptanner66-prog/Hermes-Fetch-AI.git
- Make small conventional commits after coherent test-passing chunks.
- You may push normal commits to origin main only after the full acceptance suite passes.
- Never force push, rebase published commits, amend pushed commits, use --no-verify, or run destructive git operations.
- Never stage research/repos/, research/pkgs/, research/public/, .env*, *.log, .venv/, caches, package dumps, or secrets.

Dependency pins
Use these exact/core constraints in pyproject.toml:
- Python: >=3.11,<3.13
- uagents==0.24.2
- uagents-core==0.4.4
- uagents-adapter[mcp]==0.6.2
- mcp==1.27.1
- pydantic>=2.8,<3
- PyYAML>=6,<7
- python-dotenv>=1.0,<2
- jsonschema>=4.20,<5
- httpx>=0.25,<1
Dev extras:
- pytest>=8,<9
- pytest-asyncio>=0.23,<1
- anyio>=4,<5
- ruff>=0.5
- mypy>=1.10
- types-PyYAML
Do not add unreviewed dependencies. Stop and ask before adding any new dependency.

File tree to create
pyproject.toml
README.md
LICENSE
.env.example
src/hermes_fetch_ai/__init__.py
src/hermes_fetch_ai/__main__.py
src/hermes_fetch_ai/cli.py
src/hermes_fetch_ai/config.py
src/hermes_fetch_ai/logging.py
src/hermes_fetch_ai/audit.py
src/hermes_fetch_ai/policy.py
src/hermes_fetch_ai/arg_validator.py
src/hermes_fetch_ai/result_normalizer.py
src/hermes_fetch_ai/mcp_shim.py
src/hermes_fetch_ai/fake_mcp.py
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
tests/fakes/fake_mcp_subprocess.py
docs/architecture.md
docs/security.md
docs/demo.md
docs/troubleshooting.md
docs/upstream-hermes-pr.md

Module contracts

config.py
- Pydantic v2 schema, version=1, reject unknown fields.
- Config sections: agent, hermes_mcp, policy, logging, chat.
- Defaults:
  agent.network: testnet
  agent.mode: endpoint
  agent.publish_manifest: false
  agent.enable_agent_inspector: false
  agent.dev_random_seed: false
  hermes_mcp.mode: fake
  policy.public_tools: []
  policy.allowed_senders: {}
  policy.denied_tools: []
  policy.max_args_bytes: 65536
  policy.max_output_bytes: 65536
  policy.max_list_tools_response_bytes: 65536
  policy.max_calls_per_minute_per_sender: 30
  policy.max_list_tools_per_minute_per_sender: 30
  logging.redaction: true
  chat.enable_chat: false
- Required seed behavior:
  - If agent.dev_random_seed is false, require UAGENT_SEED from env or explicit safe config field only if it is not secret-shaped in YAML. Prefer env.
  - If dev_random_seed is true, generate an ephemeral seed at startup, print only address/status, never persist seed.
  - Baseline doctor uses examples/local-direct.yaml and must pass without UAGENT_SEED because dev_random_seed=true there.
  - Mailbox config requires UAGENT_SEED and doctor/demo mailbox must fail without it.
- Hard fail if chat.enable_chat=true with NotImplementedError or validation error that states chat is out of v1 scope.
- Hard fail if hermes_mcp.mode=stdio and command is missing.
- Hard fail on secret-shaped YAML values.
- Platform default audit path:
  POSIX: ${XDG_STATE_HOME:-~/.local/state}/hermes-fetch-ai/audit.jsonl
  Windows: %LOCALAPPDATA%\HermesFetchAI\audit.jsonl

_redaction.py
- Pure helpers redact_text(s), redact_dict(d), short_sender(address).
- Redact Bearer tokens, sk-/pk- keys, JWTs, hex/base64 secrets >=32-ish, seed assignments, API key patterns.
- Do not redact uAgent addresses, but log/audit only truncated form.

logging.py
- Redacting formatter using _redaction.py.
- get_logger(name).
- No raw secret values.

audit.py
- JSONL append writer, rotate at 25 MiB, keep 5 files.
- Fields: ts, trace_id, sender_short, protocol, msg_type, tool, decision, reason, duration_ms, args_bytes, output_bytes, truncated, error_class, mode, send_status.
- Never write raw args, prompts, tool outputs, seeds, tokens, API keys, or full sender address.
- Denied attempts must be audited before return.
- Allowed attempts must be audited in finally or before send with send_status captured, so send failures do not erase the audit trail.

policy.py
- Pure policy plus in-process token buckets.
- visible_tools(sender, tools, cfg): denylist first, sender allowlist, then public_tools, else drop.
- authorize(sender, tool, args, protocol, cfg): default deny, denylist wins, sender allowlist, public_tools, rate limit.
- Rate limits apply to both list_tools and call_tool.
- default_safe_public_tools() returns {"skills_list"}, but docs must state this is demo-default only and maximum privacy can use empty public_tools.

arg_validator.py
- validate_args(tool, args, cfg) before shim invocation.
- Normalize missing inputSchema to {"type":"object","properties":{}}.
- Enforce jsonschema validation.
- Reject URL-like string args that resolve or parse to localhost/private/link-local/0.0.0.0, including IPv6 loopback/link-local/private, IPv4-mapped IPv6, and common decimal/octal/hex IP forms where feasible.
- If HTTP fetching is ever added, guard redirects and DNS resolution to private ranges. For v1, implement the parser/resolver guard and tests for representative cases.
- Reject shell metacharacters in non-shell fields unless an explicit per-tool trusted policy disables that check.

result_normalizer.py
- dataclass NormalizedToolResult(text, structured, is_error, truncated, output_bytes).
- from_call_tool_result(result: mcp.types.CallToolResult, max_bytes) for stdio/SSE/HTTP client paths.
- from_fastmcp_result(result, max_bytes) for in-process fake/Hermes FastMCP server paths.
- Concatenate text blocks.
- Preserve structuredContent/structured dict when present.
- Replace binary/image/audio/resource content with short placeholders.
- Enforce max bytes with deterministic marker: "[…truncated; original_bytes=N]".
- Mirror isError when available; otherwise infer false unless exception path.

fake_mcp.py
- Internal fake FastMCP builder used by tests and local demo.
- _build_fake_server() returns FastMCP with echo(text: str) -> str and add(a: int, b: int) -> int.
- Package code imports from this module.
- examples/fake_mcp_server.py imports/re-exports this builder. Package code must not import from examples.

mcp_shim.py
- HermesMCPClientShim(cfg, policy/output config as needed).
- Modes: fake, in_process_hermes_tools, stdio, sse, http.
- fake: use fake_mcp._build_fake_server() in process.
- in_process_hermes_tools: lazy import agent.transports.hermes_tools_mcp_server._build_server(). Treat as demo-only/private API.
- stdio: use mcp.client.stdio.stdio_client + ClientSession, StdioServerParameters, static command/args, shell=False, filtered env, per-call timeout, stderr redirected to temp/log file or null.
- sse/http: use official MCP client transports if available under mcp==1.27.1.
- Methods: async start(), aclose(), list_tools(), call_tool(name,args), async context manager.
- list_tools returns normalized list of mcp.types.Tool-like objects with inputSchema normalized.
- call_tool returns NormalizedToolResult.
- Never pass shim to MCPServerAdapter.
- Reconnect on broken stdio with bounded retries only when safe; do not blindly retry side-effecting calls unless the call did not reach the subprocess.
- Env filter:
  POSIX default: PATH, HOME, TMPDIR, HERMES_HOME, HERMES_QUIET, HERMES_REDACT_SECRETS, locale vars if needed.
  Windows default: PATH, PATHEXT, SystemRoot, WINDIR, TEMP, TMP, USERPROFILE, HERMES_HOME, HERMES_QUIET, HERMES_REDACT_SECRETS.
  Secrets are opt-in only.

direct_protocol.py
- Import only ListTools, ListToolsResponse, CallTool, CallToolResponse, mcp_protocol_spec from uagents_adapter.mcp.protocol.
- build_protocol(shim, cfg, audit, logger) returns Protocol(spec=mcp_protocol_spec, role="server").
- Use signed on_message handlers only. Do not use on_query.
- ListTools handler:
  - rate limit sender;
  - tools = await shim.list_tools();
  - filtered = policy.visible_tools(sender, tools, cfg.policy);
  - serialize with inputSchema normalized;
  - cap serialized response size;
  - audit;
  - ctx.send ListToolsResponse.
- CallTool handler:
  - compute args byte size before any shim call;
  - deny oversize before shim;
  - policy.authorize before shim;
  - denied calls audit and return error without shim invocation;
  - list/find tool;
  - validate args;
  - shim.call_tool;
  - audit output bytes/truncated/error;
  - send CallToolResponse.
- Return CallToolResponse(result=None,error=reason) for denies/errors.

registration_policies.py
- NoopRegistrationPolicy subclass compatible with uAgents registration policy interface.
- It must do nothing and never call Almanac/Agentverse.

uagent_app.py
- run_bridge(cfg): construct Agent with name, port, seed, endpoint/mailbox/proxy mode, network, registration_policy, enable_agent_inspector, readme_path, description.
- If publish_manifest false, use NoopRegistrationPolicy.
- Include exactly the bridge protocol; publish_manifest follows config.
- Assert/validate chat disabled.
- Start shim before agent, close shim on shutdown.
- Do not include MCPServerAdapter protocols. Do not instantiate chat protocol.

hermes_probe.py
- Probe without printing secrets:
  - hermes-agent import/version.
  - mcp import/version.
  - agent.transports.hermes_tools_mcp_server._build_server importable and optional tool count.
  - hermes console script path.
  - hermes mcp serve --help result, with ModuleNotFoundError: mcp_serve reported distinctly.
- Exit success if at least fake mode works for local and reports Hermes-backed status as warning/info.

cli.py
- argparse or Typer-free argparse preferred to avoid extra dependency.
- Commands:
  doctor [--config PATH] [--contamination-scan]
  probe-hermes
  serve --config PATH
  demo local
  demo mailbox
- doctor default config is examples/local-direct.yaml and must pass in clean venv without UAGENT_SEED.
- doctor for mailbox config must fail without UAGENT_SEED.
- Never print seed values or env secret values.
- demo local runs two agents in one process using dispatcher and fake MCP, prints bridge address, visible tool count, echo result, and audit event count.
- demo mailbox refuses without UAGENT_SEED and is manual only.

version_pins.py
- Constants for pins. doctor verifies exact core package versions where import metadata is available.

Examples
- examples/local-direct.yaml: fake mode, dev_random_seed=true, testnet, publish_manifest=false, enable_agent_inspector=false, public_tools=[echo].
- examples/hermes-local.yaml: in_process_hermes_tools, dev_random_seed=true, testnet, public_tools=[skills_list], denied_tools includes every other known EXPOSED_TOOLS name including web, browser, image, tts, kanban, and skill_view.
- examples/agentverse-mailbox.yaml: mailbox manual demo, dev_random_seed=false, publish_manifest=true, enable_agent_inspector=true, testnet, no chat.
- .env.example: placeholders only; no real-looking secrets.

Tests
All tests must run with:
python -m pytest -q
No hosted dependencies, no Agentverse, no Almanac, no ASI key, no Hermes install for the default suite.

Required tests:

test_config.py
- missing UAGENT_SEED rejected when dev_random_seed=false.
- dev_random_seed=true accepted without seed.
- chat.enable_chat=true rejected.
- stdio mode requires command.
- audit path defaults per platform.
- secret-shaped YAML rejected.

test_policy.py
- empty policy denies all CallTool.
- visible_tools filters unknown sender to public_tools or empty.
- allowlisted sender sees allowed tools.
- denylist beats allowlist/public.
- CallTool rate limit blocks above threshold.
- ListTools rate limit blocks above threshold.

test_arg_validator.py
- jsonschema violation raises.
- missing inputSchema normalizes to empty object schema.
- localhost/RFC1918/link-local/0.0.0.0/IPv6 loopback URL rejected.
- representative DNS/private resolution guard tested without external network, using monkeypatch.
- shell metacharacters rejected in non-shell fields.

test_result_normalizer.py
- from_call_tool_result handles text, structuredContent, isError, binary placeholder, truncation.
- from_fastmcp_result handles server-side FastMCP return shapes.
- truncation marker includes original byte count.

test_mcp_shim_fake_server.py
- fake list_tools returns echo/add.
- fake call_tool returns normalized result.
- in-process result path uses from_fastmcp_result.
- stdio fake subprocess launches with filtered env.
- Windows env allowlist includes SystemRoot/WINDIR/PATHEXT/TEMP/TMP when present.
- stderr does not contaminate protocol stdout/log output.
- timeout returns structured error.
- broken subprocess handled without leaking stderr/secrets.

test_direct_protocol_policy.py
- denied CallTool does not invoke shim.
- oversize args denied before shim.
- arg validation failure denies before shim.
- unknown sender ListTools sees only public tools or empty.
- ListTools response size cap enforced.
- audit written for deny before return and for allowed call even if send fails.

test_uagent_direct_protocol.py
- two in-process Agents with NoopRegistrationPolicy, inspector false, publish_manifest false, testnet.
- client ListTools succeeds via dispatcher.
- client CallTool(echo) returns hello.
- signed handlers only; no unsigned handler registered for bridge protocol digests.
- no MCPServerAdapter protocols included.
- no chat protocol included.
- exactly one bridge-owned MCP protocol among bridge-included protocols; do not assert against unrelated uAgents internals.

test_security_defaults.py
- Hermes-backed example exposes only skills_list publicly.
- skill_view and side-effecting tools are denied by default.
- doctor does not print seed or seed fragments.
- audit/log does not include raw args/raw output/full sender/secrets.
- publish_manifest defaults false in local/CI configs.
- no hosted network call in local demo path; monkeypatch Agentverse/Almanac endpoints to fail fast.

test_redaction.py
- Bearer, sk/pk, JWT, hex/base64 secrets, and seed assignments redacted.
- sender address shortened.

test_contamination.py
- Scan src/, docs/, examples/, README.md, .env.example, pyproject.toml.
- Forbidden: OpenClaw and private/domain-specific guardrail terms from research/CONTAMINATION_AUDIT.md.
- The word legal is allowed only in LICENSE/license boilerplate or the exact phrase legal-tech if it appears only in private research, not public docs/code.
- Carve out research/, root operator prompts, and audit files.

Docs
README.md
- Use general AI-infrastructure positioning from research/PUBLIC_POSITIONING.md.
- Explain connection project, not reinvention.
- Quickstart local demo.
- Security defaults.
- No payments/marketplace/wallet UX.

docs/architecture.md
- Final architecture, message flow, trust boundaries.
- Why existing Fetch/Hermes/MCP rails are enough.
- Why MCPServerAdapter.protocols is not used.
- Why chat is out of v1.

docs/security.md
- Threat model.
- Default deny.
- Sender identity is routing, not authorization.
- SSRF/path/shell controls.
- ListTools inventory/rate/size risks.
- Subprocess env/stderr hardening.
- Audit redaction.

docs/demo.md
- Local CI demo.
- Hermes-backed local demo.
- Agentverse/mailbox manual demo.
- Windows section: PowerShell activation, py -3.12 vs python, where hermes, paths with spaces.

docs/troubleshooting.md
- ModuleNotFoundError: mcp_serve.
- Address in use.
- Tool not allowed for sender.
- Schema validation failed.
- No UAGENT_SEED for mailbox.
- Windows executable/env/stderr issues.

docs/upstream-hermes-pr.md
- Preferred upstream shape: Hermes-native uAgents serve command/plugin.
- Platform adapter is fallback only if Hermes maintainers request it.
- Optional dependency group.
- Must run Hermes pre/post tool-call hooks upstream.
- Attribution/license for uagents_adapter.mcp.protocol imports.
- Do not port research prompts/audits/vendored evidence.

Build order
1. pyproject.toml, package skeleton, version_pins.py, .env.example, minimal README.
2. _redaction.py + tests/test_redaction.py.
3. logging.py and audit.py + audit tests.
4. config.py + tests/test_config.py.
5. policy.py + tests/test_policy.py.
6. arg_validator.py + tests/test_arg_validator.py.
7. result_normalizer.py + tests/test_result_normalizer.py.
8. fake_mcp.py, examples/fake_mcp_server.py, tests/fakes/fake_mcp_subprocess.py.
9. mcp_shim.py fake/in-process/stdio paths + tests/test_mcp_shim_fake_server.py.
10. registration_policies.py.
11. direct_protocol.py + tests/test_direct_protocol_policy.py.
12. uagent_app.py + tests/test_uagent_direct_protocol.py.
13. hermes_probe.py and cli.py + tests/test_security_defaults.py.
14. examples YAML and local_client.py.
15. docs.
16. tests/test_contamination.py.
17. README polish.
18. Final full test/doctor/demo run, commit, then normal push if clean.

Security gates
- Default deny preserved.
- Denied calls never invoke shim.
- ListTools filtered/rate-limited/capped.
- Args size/schema/SSRF validation before shim.
- Output truncation deterministic.
- Stdio env filtered, shell=False, stderr redirected.
- No raw secrets/args/outputs in logs/audit.
- No chat in v1.
- No MCPServerAdapter.protocols.
- No hosted dependency for CI.

Contamination gates
- Run tests/test_contamination.py.
- Do not add forbidden/private/domain-specific terms to public code/docs/examples/README.
- Do not add OpenClaw references.
- Do not add payment/billing/marketplace/wallet UX content.
- Do not commit research caches or secrets.

Stop/ask conditions
Stop and ask the user before continuing if:
- Any core safety test would need to be skipped or xfailed.
- A new dependency is needed.
- CI cannot pass without hosted services, Agentverse, Almanac, ASI, or real Hermes install.
- MCPServerAdapter.protocols seems necessary to make progress.
- Chat seems necessary to make progress.
- hermes mcp serve appears fixed upstream or package pins differ materially; report and ask whether to change architecture.
- uAgents/MCP/FastMCP API evidence contradicts this prompt.
- A secret is accidentally encountered; do not print it, stop and ask for remediation.

Final acceptance criteria
All must pass before final commit/push:
- python -m pytest -q
- python -m hermes_fetch_ai.cli doctor
- python -m hermes_fetch_ai.cli demo local
- python -m hermes_fetch_ai.cli doctor --contamination-scan
- ruff check . if installed
- mypy src/hermes_fetch_ai --ignore-missing-imports if installed
- git status shows only intended tracked changes.
- No forbidden files staged.
- No secrets printed or committed.
- Final push policy: after all checks pass, push normal commits with `git push origin main`. Do not force push.
```
