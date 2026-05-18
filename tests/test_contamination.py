from pathlib import Path

from hermes_fetch_ai.cli import _contamination_scan


def _public_release_files() -> list[Path]:
    roots = [
        Path("src"),
        Path("docs"),
        Path("examples"),
        Path("README.md"),
        Path(".env.example"),
        Path("pyproject.toml"),
    ]
    files: list[Path] = []
    for root in roots:
        files.extend(
            [root]
            if root.is_file()
            else [p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
        )
    return files


def test_public_tree_has_no_forbidden_contamination():
    forbidden = [
        "openclaw",
        "private project",
        "domain-specific guardrail",
        "legal-tech",
        "recovery phrase",
        "mainnet spend",
        "real fet movement",
    ]
    hits = []
    for path in _public_release_files():
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for term in forbidden:
            if term in text:
                hits.append((str(path), term))
    assert hits == []


def test_cli_contamination_scan_matches_public_tree_expectation():
    clean, detail = _contamination_scan()
    assert clean, detail
