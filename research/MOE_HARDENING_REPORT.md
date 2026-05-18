# MOE Hardening Report

Updated: 2026-05-17T03:35:34Z

## Verdict

The repo is now Teknium-facing for a local/offline and Hermes-stdio proof, within the ChatGPT-only constraint. It is not a reinvention project: Fetch/uAgents/Agentverse/Almanac/payment protocols provide the external agent rails, and Hermes remains the local intelligence and execution boundary.

The remaining non-green area is hosted mailbox proof, which is explicitly operator-owned because it requires a private seed and Agentverse account/linking actions. That blocker is validated locally rather than hand-waved.

## What changed in this MOE continuation

This continuation did not restart from scratch. It continued from `research/moe-hardening-run.log`, preserved the useful findings there, and completed the missing acceptance artifacts.

Completed or confirmed:

- Required MOE status/report artifacts were created or updated.
- Fetch GitHub sweep was refreshed against public GitHub API/raw sources.
- Hermes upstream sweep was refreshed against public GitHub API/raw sources and the local Hermes source checkout was treated as reference-only.
- Full connection gap audit was written as a bridge responsibility matrix.
- Teknium one-pager was written with a narrow upstream PR ask.
- Upstream PR execution plan was updated to reflect the current thin plugin/CLI shape and exclude broad A2A/settlement scope from PR one.
- Required verification gates were run and recorded.

No subagent MOE council was used in this continuation because the hard route required ChatGPT-only and did not authorize routing through non-ChatGPT providers.

## Current bridge shape

The repo's valuable shape is now the thin bridge:

1. Fetch/uAgents layer
   - uAgent identity/addressing and signed-message transport.
   - endpoint/mailbox/proxy modes.
   - protocol manifests and Agentverse/Almanac discovery as hosted/operator rails.

2. Bridge layer
   - versioned YAML/env config;
   - explicit policy allowlists and denylist precedence;
   - sender-filtered `ListTools`;
   - schema, size, URL, DNS, and shell-metacharacter argument validation;
   - stdio subprocess environment filtering;
   - redacted, reduced audit records;
   - default-off payment negotiation proof.

3. Hermes layer
   - `hermes mcp serve` as the real stdio seam;
   - local tools, skills, config, logging, plugins, and operator approval boundaries;
   - no new agent framework inside this repo.

## Evidence summary

### Local uAgents/MCP proof

- Command: `cmd //c ".\\.venv\\Scripts\\python.exe -m hermes_fetch_ai.cli demo local"`
- Result: exit 0.
- Output included: bridge address, `visible tool count: 1`, `echo result: hello`, `audit event count: 4`.

This proves the in-process uAgents dispatcher path and the bridge-owned MCP protocol handlers without hosted dependencies.

### Real Hermes stdio proof

- Command: `cmd //c ".\\.venv\\Scripts\\python.exe -m hermes_fetch_ai.cli doctor --config examples\\hermes-stdio-env.yaml --probe-backend"`
- Result: exit 0.
- Output: `backend: ok: 10 tools`; `doctor: ok`.

- Command: `cmd //c ".\\.venv\\Scripts\\python.exe -m hermes_fetch_ai.cli demo hermes --config examples\\hermes-stdio-env.yaml"`
- Result: exit 0.
- Output included: bridge address, `visible tool count: 2`, `conversations_list result: {"count": 0, "conversations": []}`, `audit event count: 4`.

This proves the same bridge path can call the current Hermes MCP stdio surface.

### Payment dry-run proof

- Command: `cmd //c ".\\.venv\\Scripts\\python.exe -m hermes_fetch_ai.cli demo payment-dry-run --config examples\\payment-dry-run.yaml"`
- Result: exit 0.
- Output included: payment reference, `0.01 FET via fet_direct`, `CompletePayment`, and `no real funds moved`.

This proves payment negotiation shape using official uAgents payment message models without wallet access or settlement.

### Mailbox blocker proof

- Command: `env -u UAGENT_SEED cmd //c ".\\.venv\\Scripts\\python.exe -m hermes_fetch_ai.cli doctor --config examples\\agentverse-mailbox-hermes.yaml --probe-backend"`
- Result: exit 1 as expected.
- Output: `UAGENT_SEED is required when agent.dev_random_seed=false`.

- Command: `env -u UAGENT_SEED cmd //c ".\\.venv\\Scripts\\python.exe -m hermes_fetch_ai.cli demo mailbox --config examples\\agentverse-mailbox-hermes.yaml --duration-seconds 1"`
- Result: exit 1 as expected.
- Output directs the operator to keep `UAGENT_SEED` in the shell and use `research/HOSTED_DEMO_BLOCKER.md`.

This proves the blocker is real and correctly enforced, not a stale TODO.

## Verification results

- `cmd //c ".\\.venv\\Scripts\\python.exe -m pytest -q"` -> exit 0, `77 passed in 17.94s`.
- `cmd //c ".\\.venv\\Scripts\\python.exe -m ruff check ."` -> exit 0, `All checks passed!`.
- `cmd //c ".\\.venv\\Scripts\\python.exe -m mypy src\\hermes_fetch_ai --ignore-missing-imports"` -> exit 0, `Success: no issues found in 20 source files`.
- `cmd //c ".\\.venv\\Scripts\\python.exe -m hermes_fetch_ai.cli doctor --contamination-scan"` -> exit 0, `contamination: ok`, `doctor: ok`.

## Teknium-facing framing

The strongest pitch is not "Hermes clones Agentverse" or "Fetch runs Hermes." It is:

Hermes can expose a minimal, policy-filtered MCP tool surface over Fetch/uAgents identity, addressing, mailbox/discovery, and payment negotiation rails. Fetch supplies the decentralized agent network surfaces; Hermes supplies local intelligence and operator-controlled execution.

That makes the first upstream patch small enough to review and useful enough to start a real conversation.

## Remaining blockers

Operator-owned:

- Hosted Agentverse mailbox proof.
- Remote uAgent -> mailbox -> bridge -> Hermes stdio -> response transcript.
- Any testnet funding or production settlement.
- Upstream Hermes PR branch/PR creation.

Not currently blocked locally:

- Python tests.
- Ruff.
- Mypy.
- Contamination scan.
- Hermes stdio backend probe.
- Local demo.
- Payment dry-run demo.
