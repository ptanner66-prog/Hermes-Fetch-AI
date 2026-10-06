"""The public tree stays on topic.

The public docs, code, and examples must not mention unrelated projects, and
must not describe commerce features (marketplaces, billing, payments), which
are out of scope for the bridge. This is a repository check, so it lives in
the test suite rather than in the shipped CLI.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_TREE = [
    "src",
    "docs",
    "examples",
    "hermes-plugin",
    "upstream",
    "README.md",
    ".env.example",
    "pyproject.toml",
]
FORBIDDEN = [
    "openclaw",
    "private project",
    "domain-specific guardrail",
    "legal-tech",
    "marketplace",
    "billing",
    "payment",
]


def test_public_tree_stays_on_topic():
    hits = []
    for entry in PUBLIC_TREE:
        root = ROOT / entry
        files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
        for path in files:
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            hits.extend((str(path.relative_to(ROOT)), term) for term in FORBIDDEN if term in text)
    assert hits == []
