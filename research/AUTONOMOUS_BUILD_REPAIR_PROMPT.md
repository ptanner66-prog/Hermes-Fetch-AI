You are an autonomous coding agent continuing the Hermes Fetch AI build in:
C:\Users\ptann\OneDrive\Work\Hermes Fetch AI

You are resuming after the first autonomous build intentionally stopped short. Do not restart from scratch. Preserve and harden the implementation already present in this repo.

Mission:
Finish the build to the original "perfect" acceptance bar: fully implemented and fully tested within local/offline scope, contamination-clean, docs coherent, committed and pushed to origin/main. The project philosophy remains: connection project, not reinvention. Existing Fetch/uAgents/MCP/Hermes rails first. Thinnest reliable bridge. No new agent framework. No v1 payments, marketplace sprawl, wallet UX, chat protocol, legal-tech content, or OpenClaw content.

Authoritative docs:
- Read research/FINAL_BUILD_PROMPT.md end to end.
- Read research/FINAL_ARCHITECTURE_DECISION.md.
- Read research/EXTREME_HARDENING_AUDIT.md.
- Read research/GO_NO_GO.md.
- Read research/FETCH_ACCOUNT_REQUIREMENTS.md.
- Treat this repair prompt as the latest instruction where it is stricter.

Known current state from the previous run:
- The repo has a working package scaffold, docs, examples, and tests.
- Previous checks passed in the repo .venv:
  - .venv/Scripts/python -m pytest -q: 52 passed
  - .venv/Scripts/python -m hermes_fetch_ai.cli doctor: ok
  - .venv/Scripts/python -m hermes_fetch_ai.cli demo local: ok
  - .venv/Scripts/python -m hermes_fetch_ai.cli doctor --contamination-scan: ok
  - ruff check .: pass
  - mypy src/hermes_fetch_ai --ignore-missing-imports: pass
- But the build was correctly marked incomplete because review found acceptance/security gaps.

Blocking repair list:
1. Replace fake/custom stdio MCP mode with the real MCP Python client transport:
   - Use mcp.client.stdio.stdio_client, ClientSession, and StdioServerParameters for stdio mode.
   - Preserve fake MCP only as explicit local/offline fake backend.
   - Tests must prove stdio mode builds/uses the MCP client interface without hitting hosted services.

2. Move ListTools rate limiting before any MCP/Hermes inventory query:
   - A denied or rate-limited sender must not be able to force shim.list_tools().
   - Add a regression test with a spy shim proving list_tools is not called after sender is rate-limited/denied.

3. Fix audit sender redaction:
   - Never write full sender addresses to audit output.
   - AuditWriter should own sender shortening/redaction even if callers pass sender_short incorrectly.
   - Add regression tests for long sender addresses and direct protocol call paths.

4. Make local demo and tests prove an actual in-process uAgents dispatcher round trip:
   - Use two local Agents and the uagents.dispatch.dispatcher singleton or the current uAgents local dispatch primitive.
   - Keep NoopRegistrationPolicy, publish_manifest=False, enable_agent_inspector=False, testnet defaults, and no hosted calls.
   - The local demo must not merely call protocol handler helpers directly.
   - Add tests that fail if the demo bypasses the uAgents message path.

5. Wire NoopRegistrationPolicy into Agent construction when publish_manifest=false:
   - Add tests that inspect/spy the created Agent configuration or construction path.
   - Do not allow Almanac/Agentverse registration from CI/local demo defaults.

6. Capture ctx.send success/failure in audit:
   - Audit before attempting send, then record success or failure without erasing the audit trail.
   - Add a regression test where send fails and the audit still records the attempted call and send failure.

7. Add the security-hardening gaps found by review:
   - Tool description/schema fingerprint or inventory recheck before call where appropriate.
   - Unicode/ANSI/zero-width normalization or rejection for exposed tool names and policy checks.
   - Tests for alias/confusable/control-character attempts.

8. Create or update research/BUILD_BLOCKERS.md:
   - While work is incomplete, record exact remaining blockers.
   - When all blockers are resolved, update it to say there are no remaining local/offline blockers and list the evidence commands/results.

Required final verification, all from this repo:
- .venv/Scripts/python -m pytest -q
- .venv/Scripts/python -m hermes_fetch_ai.cli doctor
- .venv/Scripts/python -m hermes_fetch_ai.cli demo local
- .venv/Scripts/python -m hermes_fetch_ai.cli doctor --contamination-scan
- .venv/Scripts/python -m ruff check .
- .venv/Scripts/python -m mypy src/hermes_fetch_ai --ignore-missing-imports
- git status --short --branch
- git log --oneline -5
- git ls-remote --heads origin main

Git rules:
- Do not commit or stage forbidden files: research/repos/, research/pkgs/, research/public/, *.log, .env, .venv, node_modules, caches, pyc.
- Do not push until all final verification commands pass.
- Normal commit and git push origin main are allowed after the final green milestone.
- No force-push, no amend of pushed commits, no --no-verify.
- If a git command is blocked by the host shell policy, write an exact safe manual handoff in research/BUILD_BLOCKERS.md and continue all non-git verification. Do not pretend it was pushed.

Hosted Fetch / Agentverse:
- Local tests and local demo must not require account, mailbox, wallet, ASI key, or FET.
- If a hosted/manual demo needs account/FET/mailbox setup, keep it in research/FETCH_ACCOUNT_REQUIREMENTS.md only with placeholders. Do not inspect or print real secrets.

Stop conditions:
- Stop only after final green, commit created, pushed to origin/main, and final output includes final commit SHA plus one-line PR-ready description.
- If blocked only by exact operator-owned external action, write research/BUILD_BLOCKERS.md with exact action needed and final output clearly saying it is operator-owned.
- Do not stop for agent-solvable blockers.
