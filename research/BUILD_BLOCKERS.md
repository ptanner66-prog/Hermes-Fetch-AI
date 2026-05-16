# Build Blockers

There are no remaining local/offline blockers for the Hermes Fetch AI build.

Resolved hardening items:
- Stdio MCP mode uses the official MCP Python client transport (`stdio_client`, `ClientSession`, `StdioServerParameters`) and keeps fake MCP as an explicit local/offline backend.
- ListTools rate limiting occurs before MCP/Hermes inventory queries.
- AuditWriter owns sender shortening even when callers pass `sender_short` directly.
- Local demo and tests exercise an in-process uAgents dispatcher round trip rather than direct protocol helper calls.
- `NoopRegistrationPolicy` is wired into Agent construction when `publish_manifest=false`.
- Protocol send success/failure is captured in audit events without erasing pre-send audit records.
- Exposed tool names and policy checks reject Unicode confusables, ANSI/control characters, and zero-width aliases; call paths perform a fresh inventory lookup/schema fingerprint immediately before invocation.

Final local/offline evidence:
- `.venv/Scripts/python -m pytest -q` -> `60 passed in 14.41s`
- `.venv/Scripts/python -m hermes_fetch_ai.cli doctor` -> `doctor: ok`
- `.venv/Scripts/python -m hermes_fetch_ai.cli demo local` -> `bridge address: agent1qtmzgg9h0smgtccdlw7xzraj7syjq802gk39xxkgl8zhuyeux9w52l6zhhl`; `visible tool count: 1`; `echo result: hello`; `audit event count: 4`
- `.venv/Scripts/python -m hermes_fetch_ai.cli doctor --contamination-scan` -> `contamination: ok`; `doctor: ok`
- `.venv/Scripts/python -m ruff check .` -> `All checks passed!`
- `.venv/Scripts/python -m mypy src/hermes_fetch_ai --ignore-missing-imports` -> `Success: no issues found in 17 source files`

Git push status: no local/offline blocker; final commit/push verification is recorded in the operator run output.
