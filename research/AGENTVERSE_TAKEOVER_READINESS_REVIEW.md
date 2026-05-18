# Agentverse Takeover Readiness Review

Status: BLOCKED_OPERATOR_ONLY
Updated: 2026-05-18T18:30:00Z

This review was run after the operator asked for a full-scale Agentverse readiness pass with independent subagent review. It does not provide legal advice and does not authorize hosted calls, payment rails, production deployment, or secret handling by the agent.

## Review Roles

- Legal/operator-risk counsel: reviewed public docs and handoff language for unsafe claims, secret-handling gaps, machine-specific paths, and operator-owned boundaries.
- Security/payment reviewer: reviewed fail-closed behavior, remote error exposure, payment dry-run claims, and demo exit semantics.
- Agentverse operations architect: reviewed official Agentverse/uAgents docs and mapped the correct sign-in path.
- Codex implementation reviewer: patched repo-local blockers and reran local acceptance gates.

## Current Verdict

The repo is ready for the operator to sign in and execute the mailbox/Inspector handoff runbook.

It is not `DONE_AGREED` because the live Agentverse mailbox link, controlled remote sender transcript, optional payment proof beyond dry-run, and PR/merge authority are operator-owned.

## Official Path Decision

Immediate path:

1. Link mailbox with `examples\agentverse-mailbox.yaml`.
2. Stop the first-link process.
3. Start the real Hermes bridge with `examples\agentverse-mailbox-hermes.yaml`.
4. Capture deny-first `ListTools` proof.
5. Optionally capture one allowlisted read-only `CallTool` proof from a controlled sender.

Deferred path:

- External ACP registration requires an ACP-compatible uAgent and public reachable endpoint.
- Hosted Agentverse agents are future wrapper/demo work, not the first proof for the local Hermes runtime.

## Repo-Local Fixes Applied

1. Empty visible tool policy now short-circuits `ListTools` without touching the backend.
2. Backend tool errors and backend exceptions now return a generic remote error instead of raw backend text.
3. Audit still records sanitized local reason data.
4. `demo hermes` and local demo now fail nonzero when the tool call returns an error or empty result.
5. Operator docs now use mailbox/Inspector as the first live proof path and remove machine-specific public paths.
6. `examples\agentverse-mailbox.yaml` is documented as first-linking only, while `examples\agentverse-mailbox-hermes.yaml` remains the real Hermes proof config.
7. Added `research\HOSTED_HOOKUP_EVIDENCE.md` so proof capture has a fixed redaction-safe template.

## Verification

| Gate | Result |
| --- | --- |
| Focused protocol/mailbox/contamination tests | `32 passed` |
| Full pytest | `97 passed` |
| Ruff | `All checks passed!` |
| Mypy | `Success: no issues found in 20 source files` |
| Hermes backend probe | `backend: ok: 10 tools`; `doctor: ok` |
| Local demo | bridge address printed; visible tool count `1`; `echo result: hello`; audit event count `4` |
| Hermes stdio demo | bridge address printed; visible tool count `2`; `conversations_list` returned count `0`; audit event count `4` |
| Payment dry-run | request created; accepted `0.01 FET via fet_direct`; `CompletePayment`; audit event count `2`; no funds moved |
| Contamination scan | `contamination: ok`; `doctor: ok` |
| No-seed mailbox negative proof | exit code `1`; failed closed on missing `UAGENT_SEED` |
| Disk after cleanup | about `2.54 GB` free on `C:` |

## Operator Sign-In Checklist

Use `docs\agentverse-operator-handoff.md` as the live runbook.

Required operator-owned actions:

1. Sign into Agentverse.
2. Enter `UAGENT_SEED` only in a clean process-local shell.
3. Run `serve --config examples\agentverse-mailbox.yaml` for first mailbox/Inspector linking.
4. Run `serve --config examples\agentverse-mailbox-hermes.yaml` for the real Hermes bridge.
5. Capture sanitized evidence in `research\HOSTED_HOOKUP_EVIDENCE.md`.
6. Stop if Agentverse asks for paid quota, wallet authorization, production deployment, or unrelated permissions.

## Remaining Blockers

- Hosted Agentverse mailbox link and transcript are not captured yet.
- Positive remote tool proof needs an operator-chosen sender and a private one-tool allowlist config.
- Payment remains CLI dry-run only unless the operator gives separate explicit approval.
- Dirty tree still needs human review before commit, PR, or merge.
