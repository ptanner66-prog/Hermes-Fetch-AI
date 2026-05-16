from pathlib import Path


def test_public_tree_has_no_forbidden_contamination():
    roots = [
        Path("src"),
        Path("docs"),
        Path("examples"),
        Path("README.md"),
        Path(".env.example"),
        Path("pyproject.toml"),
    ]
    forbidden = ["openclaw", "private project", "domain-specific guardrail", "legal-tech"]
    hits = []
    for root in roots:
        files = (
            [root]
            if root.is_file()
            else [p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
        )
        for path in files:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for term in forbidden:
                if term in text:
                    hits.append((str(path), term))
    assert hits == []
