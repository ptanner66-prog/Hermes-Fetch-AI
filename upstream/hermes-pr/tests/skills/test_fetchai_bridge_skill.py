from __future__ import annotations

import re
from pathlib import Path

SKILL_PATH = (
    Path(__file__).resolve().parents[2]
    / "optional-skills"
    / "autonomous-ai-agents"
    / "fetchai-bridge"
    / "SKILL.md"
)


def _frontmatter() -> str:
    text = SKILL_PATH.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md must start with YAML frontmatter"
    return match.group(1)


def test_description_is_hardline_compliant():
    fm = _frontmatter()
    match = re.search(r"^description: (.*)$", fm, re.MULTILINE)
    assert match, "frontmatter must declare a description"
    description = match.group(1).strip()
    assert len(description) <= 60, f"description too long: {len(description)}"
    assert description.endswith(".")
    banned = ("powerful", "comprehensive", "seamless", "advanced")
    assert not any(word in description.lower() for word in banned)


def test_frontmatter_declares_name_and_terminal_requirement():
    fm = _frontmatter()
    assert re.search(r"^name: fetchai-bridge$", fm, re.MULTILINE)
    assert "requires_toolsets: [terminal]" in fm
    assert "UAGENT_SEED" in fm


def test_sections_follow_modern_order():
    body = SKILL_PATH.read_text(encoding="utf-8")
    sections = [
        "## When to Use",
        "## Prerequisites",
        "## How to Run",
        "## Quick Reference",
        "## Procedure",
        "## Pitfalls",
        "## Verification",
    ]
    positions = [body.index(s) for s in sections]
    assert positions == sorted(positions)


def test_prose_routes_commands_through_terminal_tool():
    body = SKILL_PATH.read_text(encoding="utf-8")
    assert "`terminal`" in body
    assert "hermes fetchai demo local" in body


def test_no_secret_values_in_skill():
    body = SKILL_PATH.read_text(encoding="utf-8").lower()
    assert "sk-" not in body
    assert not re.search(r"[a-f0-9]{48,}", body)
