# Hermes Fetch AI After-Repo-Setup Prompt

```text
You are continuing work in the Hermes Fetch AI repository.

Working directory:
C:\Users\ptann\OneDrive\Work\Hermes Fetch AI

Mission:
After the repository is initialized and connected to GitHub, verify the repo plumbing, protect the public/private boundary, then continue the research-to-build workflow for Hermes Fetch AI until the output is production-grade enough to put in front of the CEO of Hermes Agent.

Context:
Hermes Fetch AI is a standalone bridge project for exposing Hermes Agent through Fetch.ai uAgents / Agentverse / Almanac. The standalone repo should be built privately until it works end-to-end. Once proven, it can be made public. After that, only the Hermes-native slice should be upstreamed to Hermes as a clean plugin/platform PR.

Core philosophy:
This is a connection project, not a reinvention project. Fetch.ai was built for agent identity, discovery, addressing, and agent-to-agent rails. Hermes already has local agent intelligence, tools, MCP, and execution boundaries. The job is to find the existing rail, verify it, wrap it cleanly, document it, and make the connection reliable.

Default bias:
- Assume the connection may already mostly exist through existing Fetch/uAgents/MCP primitives.
- Research existing rails before proposing new architecture.
- Prefer the thinnest bridge that works over a clever new subsystem.
- Treat packaging, safety defaults, docs, examples, and demo quality as the likely value-add.
- Keep the public story understated, useful, and obvious in hindsight: "Hermes supplies the local agent/execution environment; Fetch supplies the public agent network; Hermes Fetch AI connects them."

Hard boundary:
OpenClaw is out of scope. Do not include OpenClaw architecture, references, examples, README language, PR framing, implementation plans, or source material.

Repo verification tasks:
1. Confirm the current directory is the Hermes Fetch AI repo.
2. Confirm `git status --short --branch`.
3. Confirm the configured `origin` remote.
4. If the GitHub repo exists and push access works, stage and commit the current prompt/research setup with:
   `chore: initialize Hermes Fetch AI research workspace`
5. If the remote does not exist or push fails, do not burn time on GitHub plumbing. Record the exact blocker in `research/REPO_SETUP_STATUS.md` and continue local work.
6. Never commit `.env`, secrets, caches, logs, virtualenvs, node_modules, credentials, private legal-tech content, or unrelated project files.

Research continuation tasks:
1. Inspect the existing `research/` folder.
2. Continue or complete the research deliverables from `HERMES_RESEARCH_PROMPT.md`.
3. Prefer public official docs, public GitHub source, public issues/PRs, package metadata, and the local Hermes source only where directly relevant.
4. Keep source links for all important claims.
5. If any deliverable already exists, improve it rather than duplicating it.
6. Do not stop at a thin summary. The final research must be expert-level, implementation-ready, and adversarially reviewed.
7. Use web and GitHub/source evidence as a hard requirement. If web/GitHub tools are unavailable or failing, debug the tool access, document the blocker, and use the best available public-source fallback only after proving the direct path is blocked.
8. The final dossier must include enough evidence for a maintainer-quality build plan: exact APIs, version risks, source links, repo paths, test strategy, security defaults, and a staged upstream PR plan.
9. Explicitly answer whether the connection is already mostly built through `uagents-adapter`, MCPServerAdapter, FastMCP, Hermes MCP, Agentverse, or other existing rails.
10. If the connection is already mostly built, identify the missing thin layer: Hermes-specific packaging, config, safety, docs, examples, tests, demo, or upstream adapter shape.
11. If a new bridge is required, prove why the existing rails are insufficient and keep the bridge as small as possible.

Production-grade quality gate:
Do not mark this work complete unless all of the following are true:
1. `research/RESEARCH_INDEX.md` or equivalent source index contains official docs, package metadata, and GitHub source/issues/PRs where relevant.
2. Every major architectural recommendation has citations or local source-file references.
3. The Fetch/uAgents/MCP adapter path is resolved to a concrete first implementation path, or the unresolved blocker is precisely named with the next command/research step.
4. The Hermes MCP surface is documented from actual Hermes source/docs, not assumption.
5. The standalone repo plan is directly buildable by an agentic coding run without needing a human to re-research the basics.
6. The upstream Hermes PR plan is separate, narrow, and maintainer-native.
7. The security model treats Agentverse/uAgents discovery as identity, not trust.
8. `research/CONTAMINATION_AUDIT.md` exists and is honest.
9. No OpenClaw architecture or legal-tech-specific content has leaked into public-facing docs.
10. `research/BUILD_PROMPT.md` is strong enough to hand to a coding agent for the full standalone build.

Two-sided mastery requirement:
The final plan must prove deep understanding of both sides of the bridge.

Hermes-side codebase literacy:
- Map the actual Hermes code paths that matter for MCP, tools, plugin registration, gateway/platform adapters, config loading, logging, secrets, tests, and docs.
- Cite concrete Hermes files/classes/functions where relevant.
- Explain what the standalone repo should borrow conceptually from Hermes and what should stay outside Hermes until the later upstream PR.
- Explain how the eventual upstream PR should read as Hermes-native code, not a pasted external app.

Fetch-side rails literacy:
- Map uAgents identity, seeds, addresses, protocols, message models, mailbox mode, endpoint/proxy mode, Agentverse registration, Almanac discovery, ASI:One/chat integration where relevant, hosted dependencies, local dev modes, and version risks.
- Cite official Fetch/uAgents docs, package metadata, and GitHub/source references.
- Explain the exact rails for inbound and outbound message flow, including discovery, addressing, envelopes, auth/trust boundaries, and failure modes.
- Identify which Fetch rails are required for v1, optional for demo, and explicitly deferred.

Bridge synthesis:
- Produce a concrete message-flow diagram or step sequence for remote uAgent/Agentverse -> Hermes Fetch AI -> Hermes MCP/agent -> response.
- Identify every trust boundary and every place a credential or external identity appears.
- Explain the minimal viable path and the production-grade path separately.
- Avoid architecture that is elegant on paper but impossible to test locally.
- Preserve the core philosophy: existing rails first, thinnest reliable connection, no overbuilt framework, no unnecessary marketplace/payment expansion in v1.

Security / contamination rules:
You may apply abstract security lessons from legal-tech work:
- confidentiality-first design
- auditability
- least privilege
- default-deny external access
- secret redaction
- operator approval before sensitive actions
- clean public/private boundaries
- cautious public claims
- threat modeling for untrusted external agents

Do not include legal-tech-specific facts, case details, client material, MG/citator architecture, proprietary workflows, prompts, datasets, private repo names, credentials, or private strategy.

Before committing or declaring publish-ready, search the repo for:
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

For every match, either remove it or document why it is safe and necessary in `research/CONTAMINATION_AUDIT.md`.

Build planning tasks:
After the research files are coherent, create or refine `research/BUILD_PROMPT.md` so a later coding run can build the whole standalone repo. That build prompt must:
1. Keep v1 narrow.
2. Exclude payments, billing, marketplace pricing, wallet UX beyond minimum identity requirements, per-skill manifests, legal-tech use cases, and OpenClaw.
3. Preserve a clean boundary between reusable bridge logic and standalone runner/demo code.
4. Include tests, docs, security defaults, and E2E demo criteria.
5. Include a later upstream Hermes PR plan, but keep it separate from the standalone repo.

Final answer format:
1. Repo status.
2. Whether commit/push succeeded or what blocked it.
3. Research files created/updated.
4. Top unresolved blockers.
5. Evidence that web/GitHub/source research was used.
6. Exact next build prompt.
```
