# Contamination Audit

Date accessed: 2026-05-16

## Scope scanned

I scanned the safe, non-ignored repository files reported by:

```bash
git ls-files --others --exclude-standard
```

Final scan scope contained 20 safe untracked, non-ignored files. Generated evidence caches and local logs are intentionally ignored by `.gitignore`:

- `research/pkgs/`
- `research/repos/`
- `research/public/`
- `*.log`

These caches were useful for local research but should not be committed or treated as public-facing project content.

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

## Final scan counts over safe non-ignored files

```text
MG: 9 matches / 4 files
Motion Granted: 6 matches / 4 files
citator: 9 matches / 4 files
client: 112 matches / 17 files
PACER: 6 matches / 4 files
Clay: 6 matches / 4 files
legal: 19 matches / 4 files
Tannerize: 6 matches / 4 files
private repo names: 9 matches / 4 files
credentials: 19 matches / 6 files
OpenClaw: 18 matches / 5 files
```

## Results and disposition

### Guardrail-only terms

The following terms appear only in setup prompts or build/audit guardrails that explicitly say what must not be included:

- `MG`
- `Motion Granted`
- `citator`
- `PACER`
- `Clay`
- `Tannerize`
- `private repo names`

Files:

- `AFTER_REPO_SETUP_PROMPT.md`
- `HERMES_RESEARCH_PROMPT.md`
- `research/BUILD_PROMPT.md`
- this audit file

Disposition: safe for the current private-first research workspace as exclusion/guardrail text, not as architecture/source material. These files are not README/product positioning. If the repository is made public, remove the original operator prompts or replace them with neutral project guardrails that omit private-context keywords.

### `OpenClaw`

Occurrences are limited to explicit out-of-scope/anti-contamination language in:

- `AFTER_REPO_SETUP_PROMPT.md`
- `HERMES_RESEARCH_PROMPT.md`
- `research/BUILD_PROMPT.md`
- `research/V1_SCOPE.md`
- this audit file

Disposition: safe because there is no architecture, example, source material, README language, or implementation plan using it. It appears only to exclude it. Before publication, remove original prompts and retain only neutral scope language.

### `legal`

Occurrences are limited to:

- original prompt guardrails forbidding domain-specific/private content;
- `research/BUILD_PROMPT.md` hard exclusion of domain-specific/private workflow content;
- this audit file.

Disposition: safe. No domain-specific examples, case material, datasets, or proprietary workflows were included.

### `client`

Many matches are legitimate generic engineering uses:

- MCP client shim;
- local uAgent client example;
- SDK client transports such as `ClientSession` and `stdio_client`;
- adapter/client lifecycle discussion;
- test/demo client terminology.

Disposition: safe. No customer/client material appears.

### `credentials`

Matches are legitimate security/secret-handling references:

- do not commit credentials;
- Agentverse/ASI/Hermes credential boundaries;
- redaction and audit requirements.

Disposition: safe. No actual credential values were found or added.

## Public/private boundary status

- No `.env`, private key, cache, log, virtualenv, `node_modules`, credential file, or unrelated private project file is intended for commit.
- `.gitignore` excludes research package/source caches and logs.
- Public-facing project framing is general AI infrastructure: Hermes Agent + Fetch.ai uAgents / Agentverse / Almanac.
- No private domain-specific architecture, case detail, dataset, prompt, proprietary workflow, or private repo name was added to the implementation-facing deliverables.
- A read-only adversarial review flagged one important public-boundary/security issue: unmodified `MCPServerAdapter.protocols` is sender-blind after handler dispatch and should not be the production security boundary. The research/build docs were updated to require a bridge-owned policy-aware direct protocol, sender-filtered `ListTools`, disabled-by-default chat, and redacted logs.

## Remaining caution before publication

Before making the repository public, remove or rewrite the original operator prompt files if they are not needed. They contain guardrail keywords that are safe for private setup but unnecessary in a public repo. Public README/docs should instead use neutral language from `research/PUBLIC_POSITIONING.md`, `research/V1_SCOPE.md`, and `research/SECURITY_MODEL.md`.
