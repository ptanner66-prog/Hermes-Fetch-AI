from __future__ import annotations

import re

# The MCP specification recommends tool names of 1 to 128 characters.
MAX_TOOL_NAME_LENGTH = 128
_TOOL_NAME_RE = re.compile(r"[A-Za-z0-9_.-]+")


def validate_tool_name(name: str) -> str:
    """Return ``name`` if it is a safe tool name, else raise ValueError.

    Tool names are policy identifiers, so only plain ASCII letters, digits,
    ``_``, ``.`` and ``-`` are accepted. That rules out look-alike Unicode,
    zero-width and control characters, and ANSI escapes, so the name a caller
    sees is always the name that was authorized.
    """
    if not isinstance(name, str) or not _TOOL_NAME_RE.fullmatch(name):
        raise ValueError("unsafe tool name")
    if len(name) > MAX_TOOL_NAME_LENGTH:
        raise ValueError("tool name too long")
    return name


def audit_tool_name(name: object) -> str:
    """A bounded form of a caller-supplied tool name, for audit records."""
    text = str(name)
    if len(text) <= MAX_TOOL_NAME_LENGTH:
        return text
    return text[:MAX_TOOL_NAME_LENGTH] + "…"
