# PR review + official docs run prompt

Runtime route constraint:
- Provider: openai-codex
- API mode: codex_responses
- Model: gpt-5.5
- ChatGPT-only; no fallback providers or model switches unless the operator explicitly authorizes a switch.

Target repository:
- C:\Users\ptann\OneDrive\Work\Hermes Fetch AI

Hermes repo:
- C:\Users\ptann\OneDrive\Work\hermes-agent-main

Mode:
- REVIEW PLUS DOCS AUTHORING

Patch authority:
- Allowed: documentation and review artifacts under docs/ and research/; README.md only if needed to link official docs.
- Forbidden in this pass: implementation/test/config edits under src/, tests/, examples/, pyproject.toml, .github/, or config files.

Mission:
- Review current branch and full dirty worktree as the PR candidate for a narrow Hermes upstream bridge.
- Verify filesystem/command evidence; do not assume local notes are accurate.
- Author PR-ready review artifacts and user-facing docs.

Authority summary:
- Connection project, not reinvention.
- Fetch/uAgents/Agentverse/Almanac own identity, discovery, addressing, endpoint/mailbox/proxy delivery, protocols, A2A launch surfaces, manifests, wallet/network context, and payment negotiation.
- Hermes owns local intelligence, MCP, tools, safety, config, logging, plugins, and operator boundaries.
- Thinnest reliable bridge.
- No OpenClaw content.
- No legal-tech/private project content in public outputs.
- No real FET movement without explicit operator approval.

Required self-audit:
- Findings first with file:line evidence, impact, minimal fix.
- GAPs separate from defects.
- Exact checks and outcomes.
- Docs must not overclaim hosted proof or payment settlement.
- Global route docs must say gpt-5.5 and no fallback unless operator explicitly switches.
