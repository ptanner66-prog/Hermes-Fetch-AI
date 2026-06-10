# Field Test Evidence: bridge vs real hermes-agent

Date: 2026-06-10. Environment: Linux container, Python 3.11.15.

## Setup

- `hermes-agent` cloned from `NousResearch/hermes-agent` main (v0.16.x era) and
  installed with `pip install -e ".[mcp]"` into an isolated venv
  (`/tmp/hermes-venv`). Install succeeded cleanly; 25 pinned base deps + mcp extra.
- `HERMES_HOME=/tmp/hermes-home` with two bundled skills staged
  (`research/arxiv`, `productivity/ocr-and-documents`).
- Bridge config: `examples/hermes-stdio.yaml` with `hermes_mcp.command`
  overridden to `/tmp/hermes-venv/bin/python`. The bridge's stdio env
  allowlist forwards `HERMES_HOME` to the subprocess.

## Observed results (full uAgent dispatcher path, signed handlers)

1. Real server inventory in a keyless environment (check_fn gating active):
   `['skill_view', 'skills_list', 'text_to_speech']` — browser/web/vision/
   kanban tools were not served because their prerequisites are absent.
2. `ListTools` through bridge policy for an unknown sender: `['skills_list']`.
3. `CallTool skills_list args={}` was rejected by schema validation: the
   served inputSchema requires a single `kwargs` object (Hermes FastMCP
   handlers take `**kwargs`). This is the server's argument contract.
4. `CallTool skills_list args={"kwargs": {}}` succeeded:

   ```json
   {"success": true, "skills": [
     {"name": "arxiv", "description": "Search arXiv papers by keyword, author, category, or ID.", "category": null},
     {"name": "ocr-and-documents", "description": "Extract text from PDFs/scans (pymupdf, marker-pdf).", "category": null}],
    "categories": [], "count": 2,
    "hint": "Use skill_view(name) to see full content, tags, and linked files"}
   ```

5. `CallTool web_search` denied by policy (`tool denied`) before any server
   invocation, per `denied_tools`.
6. Redacted audit recorded 6+ events across the run.

## Permanent artifacts

- `tests/test_field_hermes_stdio.py` — gated integration test
  (`HERMES_FETCH_FIELD_TEST=1` + `HERMES_FETCH_HERMES_PYTHON`); passed in 3.63s
  against the real install; skips in CI.
- Wheel-install proof: `python -m build --wheel`, installed into a fresh venv,
  `demo local` and `doctor` pass from `/` with no repo checkout (packaged
  default config via `hermes_fetch_ai/data/local-direct.yaml`).
- Operator runbook and pitfalls: `docs/demo.md`.
