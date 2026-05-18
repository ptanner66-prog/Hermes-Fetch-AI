# Compliance Matrix

| Requirement | Status | Evidence |
| --- | --- | --- |
| Read required Hermes prompting guides before touching target repo | MET | Read PROMPTING_GUIDE.md, hermes-reviewer-prompting.md, and HERMES-LEASH-PROMPT-TEMPLATE.md before creating target artifacts. |
| Create run directory with prompt.md, run-state.txt, compliance-matrix.md | IN_PROGRESS | This file, prompt.md, and run-state.txt created under research/pr-review-official-docs/. |
| Keep run-state current | IN_PROGRESS | run-state.txt set to status=running. |
| Inspect git status/log/diff/untracked | PENDING | Raw command outputs not captured yet. |
| Review changed implementation files in full where behavior matters | PENDING | Not yet complete. |
| Review docs/research for contradictions | PENDING | Not yet complete. |
| Run required verification commands or record blockers | PENDING | Not yet complete. |
| Author PR review/status/upstream/checklist artifacts | PENDING | Not yet complete. |
| Author official docs under docs/ | PENDING | Not yet complete. |
| No implementation/test/config edits | IN_PROGRESS | Enforced by patch authority; final git status will verify. |
| Self-audit no secrets/OpenClaw/private content/overclaims/fallback drift | PENDING | To run after docs/artifacts are written. |
