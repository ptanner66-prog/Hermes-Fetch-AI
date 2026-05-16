# Contamination Audit
Date accessed: 2026-05-16
Re-run after the adversarial hardening pass. Adds three new public-safe files (`HARDENING_AUDIT.md`, `HARDENED_ARCHITECTURE_DECISION.md`, `HARDENED_BUILD_PROMPT.md`) and an updated `OPEN_QUESTIONS.md`. Vendored evidence under `research/repos/`, `research/pkgs/`, `research/public/`, and any `*.log` remains git-ignored and is not in scope.
## Scope scanned
- Every tracked file in `git ls-files`.
- Every safe untracked file in `git ls-files --others --exclude-standard` (currently zero outside ignored caches).
- New files added by this hardening pass:
  - `research/HARDENING_AUDIT.md`
  - `research/HARDENED_ARCHITECTURE_DECISION.md`
  - `research/HARDENED_BUILD_PROMPT.md`
  - This updated `research/CONTAMINATION_AUDIT.md`.
Out-of-scope (intentionally ignored): `research/repos/`, `research/pkgs/`, `research/public/`, `*.log`, `.env`, virtualenvs, caches.
## Terms searched
- `MG`
- `Motion Granted`
- `citator`
- `client`
- `PACER`
- `Clay`
- `legal`
- `Tannerize`
- `private repo names`
- `credentials`
- `OpenClaw`
## Counts over safe non-ignored files
(Verified by `Grep` over the repository, excluding `research/pkgs/**`.)
| Term | Files matched | Where |
|---|---|---|
| MG | 5 | operator prompts + guardrail audits |
| Motion Granted | guardrail audits only |  |
| citator | guardrail audits only |  |
| client | many | engineering uses: MCP client, ClientSession, local client uAgent, stdio_client |
| PACER | guardrail audits only |  |
| Clay | guardrail audits only |  |
| legal | guardrail audits only |  |
| Tannerize | guardrail audits only |  |
| private repo names | guardrail audits only |  |
| credentials | several | security/secret-handling text only |
| OpenClaw | guardrail audits only |  |
## Disposition
### Guardrail-only terms (`MG`, `Motion Granted`, `citator`, `PACER`, `Clay`, `Tannerize`, `private repo names`, `OpenClaw`)
Appear only in operator prompts at the repo root and in audit/guardrail text that names the forbidden term to enforce its exclusion. They are NOT present in any architecture, source, build, security, or public-positioning deliverable. Safe for the current private-first workspace.
Pre-publication action (before the repo goes public): remove the original operator prompt files (`HERMES_RESEARCH_PROMPT.md`, `AFTER_REPO_SETUP_PROMPT.md`) and replace any audit references with neutral wording that does not echo the keywords. `research/HARDENED_BUILD_PROMPT.md` and `research/HARDENING_AUDIT.md` already use the keywords only as forbidden-term lists; that pattern is acceptable in a private-first research workspace but should be sanitized to a neutral phrasing on first public release.
### `legal`
Appears only in:
- operator prompts forbidding legal-tech / domain-specific content;
- the build prompt's hard-exclusion list;
- the contamination audit.
No domain-specific legal content was added to any implementation-facing deliverable. The hardened build prompt (`research/HARDENED_BUILD_PROMPT.md`) is the new authoritative implementation prompt and contains the same forbidden-term list to ensure the autonomous build does not generate any.
### `client`
Engineering uses only:
- MCP client shim (`HermesMCPClientShim`).
- Local uAgent client example (`examples/local_client.py` in the build plan).
- SDK client transports (`ClientSession`, `stdio_client`, `sse_client`, `streamablehttp_client`).
- Adapter/client lifecycle discussion in research.
Safe. No customer/client material appears.
### `credentials`
Security-only uses:
- Do-not-commit-credentials warnings.
- Agentverse / ASI / Hermes credential boundary descriptions.
- Redaction and audit-log requirements.
Safe. No actual credential values appear anywhere in tracked files. `.env.example` (to be created by the build prompt) is required to contain placeholders only.
## Public/private boundary status
- `.gitignore` excludes `.env`, `.env.*`, keys, certificates, caches, logs, virtualenvs, vendored research caches.
- No `.env` or secret file is intended for commit.
- The autonomous build is required (by `tests/test_contamination.py`) to fail CI if any forbidden term appears in `src/`, `docs/`, `examples/`, `README.md`, `.env.example`, `pyproject.toml`, or `LICENSE`. The carve-out for `research/`, the operator prompts, and the audit files is explicit and limited.
- The hardening audit flagged one important public-boundary/security issue: unmodified `MCPServerAdapter.protocols` is sender-blind after handler dispatch and would be unsafe as the production security boundary. This is addressed by the hardened plan, which bans `adapter.protocols` from `uagent_app.py` and requires a bridge-owned policy-aware `Protocol(spec=mcp_protocol_spec, role="server")` with sender-filtered `ListTools` and policy-checked `CallTool` paths.
## Verification of new hardening files
I scanned the three new deliverables against the same forbidden-term list:
- `research/HARDENING_AUDIT.md`: matches limited to (a) explicit forbidden-term lists, (b) the OpenClaw rule, (c) the word "credentials" in security context. No new contamination introduced.
- `research/HARDENED_ARCHITECTURE_DECISION.md`: no forbidden terms outside the standard "out of scope" list (OpenClaw, legal-tech, payments). No domain-specific or private content.
- `research/HARDENED_BUILD_PROMPT.md`: explicit forbidden-term list mirrors this audit; no inline contamination.
## Remaining caution before publication
Before making the repository public:
1. Remove the two operator prompt files (`HERMES_RESEARCH_PROMPT.md`, `AFTER_REPO_SETUP_PROMPT.md`) or replace them with neutral READMEs that do not echo private guardrail keywords.
2. Trim `research/HARDENED_BUILD_PROMPT.md`, `research/HARDENING_AUDIT.md`, and this audit file to use a neutral phrasing for forbidden terms (e.g. "private-context terms" rather than listing them by name).
3. Re-run the `Grep` scan; expected outcome is zero matches outside the (then-neutralized) audit text.
4. Ensure the README/docs/positioning use only the language in `research/PUBLIC_POSITIONING.md`.
These steps are not required before the autonomous build session begins; they are required before any public publication.
