# Extreme Hardening Prompt

```text
You are Hermes running an extreme adversarial hardening pass for Hermes Fetch AI.

Working directory:
C:\Users\ptann\OneDrive\Work\Hermes Fetch AI

Mission:
Harden the Hermes Fetch AI plan far beyond the current pass, then produce a GO/NO-GO decision for autonomous implementation. This is a high-stakes public open-source project intended to be credible to Hermes Agent and Fetch.ai engineers. Treat the existing hardened plan as strong but not sacred.

Core philosophy:
This is a connection project, not a reinvention project. Fetch supplies agent identity, addressing, discovery, Agentverse/Almanac rails, mailbox/proxy/endpoint modes, and uAgent protocols. Hermes supplies local agent intelligence, tools, MCP, configuration, redaction, and execution boundaries. This repo supplies the thinnest policy-aware bridge.

Authoritative inputs:
- research/HARDENING_AUDIT.md
- research/HARDENED_ARCHITECTURE_DECISION.md
- research/HARDENED_BUILD_PROMPT.md
- research/RESEARCH_INDEX.md
- research/HERMES_MCP_SURFACE.md
- research/FETCH_UAGENTS_SURFACE.md
- research/MCP_ADAPTER_INVESTIGATION.md
- research/MCP_ADAPTER_SPIKE_PLAN.md
- research/E2E_DEMO_PLAN.md
- research/SECURITY_MODEL.md
- research/UPSTREAM_PR_PLAN.md
- research/OPEN_QUESTIONS.md
- research/CONTAMINATION_AUDIT.md

Hard rules:
- Do not write implementation code in this pass.
- Do not include OpenClaw architecture, examples, docs, or source material.
- Do not include legal-tech/private project content.
- Do not weaken the default-deny model.
- Do not accept `MCPServerAdapter.protocols` as the v1 security boundary.
- Do not enable chat protocol in v1.
- Do not invent a new agent framework.
- Do not add payment, billing, marketplace, wallet UX, or per-skill commercial manifests.
- Do not print, inspect, or write secrets.

Required investigations:
1. Re-read the hardened plan and identify every remaining way the build could fail after days of autonomous work.
2. Re-verify source claims against local public-source evidence under `research/repos/` and `research/pkgs/` where present.
3. Re-check current public docs/package metadata only when needed to resolve uncertainty. Prefer official docs/source.
4. Audit uAgents/FastMCP/MCP exact APIs that the build prompt relies on:
   - `uagents.Agent` constructor and run methods
   - `Protocol(spec=..., role="server")`
   - signed `on_message` handlers
   - dispatcher/in-process local test path
   - `uagents_adapter.mcp.protocol` message symbols
   - `mcp.ClientSession.call_tool`
   - FastMCP `list_tools`, `call_tool`, and in-process use
5. Audit Hermes exact APIs that the build prompt relies on:
   - `agent.transports.hermes_tools_mcp_server._build_server`
   - `EXPOSED_TOOLS`
   - Hermes MCP client/server packaging blocker
   - redaction/logging/config conventions
   - upstream PR shape
6. Stress-test Windows compatibility:
   - PowerShell paths with spaces
   - Python 3.11/3.12
   - subprocess stdio handling
   - temp files/audit paths
   - event loops/daemon threads
7. Stress-test CI feasibility:
   - no hosted Agentverse/Almanac dependency
   - no ASI key
   - no Hermes install for unit suite
   - deterministic in-process two-agent dispatch
8. Stress-test security:
   - sender spoofing assumptions
   - default-deny tool inventory
   - arg schema validation
   - SSRF/local-network URL defense
   - subprocess env filtering
   - stderr leakage
   - audit log redaction
   - output truncation
   - rate limiting
   - seed/address handling
9. Stress-test maintainability:
   - minimal bridge surface
   - no vendored SDK internals
   - clean upstream path
   - clear docs and examples
10. Stress-test autonomous build prompt:
   - every module has enough detail to implement
   - every test has a feasible assertion
   - no contradictions remain
   - no stale "remote does not exist" assumptions remain

Deliverables:
1. Create `research/EXTREME_HARDENING_AUDIT.md`.
   Include:
   - executive verdict
   - remaining blocking issues
   - resolved issues
   - high-risk API assumptions
   - security failure modes
   - CI failure modes
   - Windows failure modes
   - upstream PR concerns
   - exact corrections applied

2. Create `research/FINAL_ARCHITECTURE_DECISION.md`.
   This supersedes `research/HARDENED_ARCHITECTURE_DECISION.md`.
   It must include:
   - final architecture
   - why existing rails are enough
   - exact thin layer this repo adds
   - exact message flow
   - exact trust boundaries
   - exact local CI path
   - exact Hermes-backed demo path
   - exact Agentverse/manual demo path
   - final confidence level

3. Create `research/FINAL_BUILD_PROMPT.md`.
   This supersedes `research/HARDENED_BUILD_PROMPT.md`.
   It must be directly executable by an autonomous coding agent for days if needed.
   It must include:
   - build order
   - file tree
   - dependency pins
   - module contracts
   - API notes
   - tests
   - docs
   - demos
   - security gates
   - contamination gates
   - git rules
   - stop/ask conditions
   - final acceptance criteria
   - normal push policy now that `origin/main` exists

4. Update `research/OPEN_QUESTIONS.md`.
   There must be no unresolved P0/P1 blockers before GO. If there are blockers, status must be NO-GO.

5. Update `research/CONTAMINATION_AUDIT.md`.
   Include all new final files in the scan.

6. Create `research/GO_NO_GO.md`.
   It must contain exactly one of:
   - `STATUS: GO`
   - `STATUS: NO-GO`

   If GO, include:
   - one-paragraph rationale
   - final build prompt path
   - remaining non-blocking risks

   If NO-GO, include:
   - exact blockers
   - exact next actions
   - whether the autonomous build must be paused

Patch rules:
- Patch existing research files only when correcting contradictions or stale instructions.
- Do not rewrite everything for style.
- Prefer surgical corrections.

Completion standard:
Do not stop until the GO/NO-GO file exists and is honest. If the autonomous build would waste days because of an unresolved API or security uncertainty, write `STATUS: NO-GO`.

Final response:
Return only:
1. GO/NO-GO status.
2. Files created/updated.
3. Top 5 hardening corrections.
4. Exact next autonomous build prompt path if GO.
```
