from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

_OMITTED_CONTENT_TYPES = {"image", "audio", "resource", "resource_link"}


@dataclass
class NormalizedToolResult:
    """A tool result as the bridge returns it: text, capped at ``max_output_bytes``."""

    text: str
    is_error: bool
    truncated: bool
    output_bytes: int  # size before truncation


def _cap(text: str, max_bytes: int) -> tuple[str, bool, int]:
    raw = text.encode("utf-8")
    original = len(raw)
    if original <= max_bytes:
        return text, False, original
    marker = f"[…truncated; original_bytes={original}]"
    marker_raw = marker.encode("utf-8")
    if max_bytes <= 0:
        return "", True, original
    if len(marker_raw) > max_bytes:
        short_marker = "…"
        if len(short_marker.encode("utf-8")) <= max_bytes:
            return short_marker, True, original
        return "", True, original
    keep = max_bytes - len(marker_raw)
    return raw[:keep].decode("utf-8", errors="ignore") + marker, True, original


def _result(text: str, is_error: bool, max_bytes: int) -> NormalizedToolResult:
    capped, truncated, original = _cap(text, max_bytes)
    return NormalizedToolResult(capped, is_error, truncated, original)


def text_result(text: str, max_bytes: int) -> NormalizedToolResult:
    """A successful plain-text result, capped like any tool output."""
    return _result(text, False, max_bytes)


def error_result(text: str, max_bytes: int) -> NormalizedToolResult:
    """Return a tool error result capped to the same byte limit as normal output."""
    return _result(text, True, max_bytes)


def _field(block: Any, name: str) -> Any:
    return block.get(name) if isinstance(block, dict) else getattr(block, name, None)


def _extract_content(content: Any) -> str:
    """Join MCP content blocks into text; binary content is replaced by a placeholder."""
    blocks = content if isinstance(content, list | tuple) else [content]
    parts: list[str] = []
    for block in blocks:
        if block is None:
            continue
        text = _field(block, "text")
        kind = _field(block, "type")
        if text is not None:
            parts.append(str(text))
        elif kind in _OMITTED_CONTENT_TYPES:
            parts.append(f"[{kind} content omitted]")
        else:
            parts.append(str(block))
    return "\n".join(parts)


def _text_or_structured(text: str, structured: Any) -> str:
    if not text and structured is not None:
        return json.dumps(structured, sort_keys=True, default=str)
    return text


def from_call_tool_result(result: Any, max_bytes: int) -> NormalizedToolResult:
    """Normalize an MCP client ``CallToolResult``."""
    structured = _field(result, "structuredContent") or _field(result, "structured_content")
    text = _text_or_structured(_extract_content(_field(result, "content")), structured)
    is_error = bool(_field(result, "isError") or _field(result, "is_error"))
    return _result(text, is_error, max_bytes)


def from_fastmcp_result(result: Any, max_bytes: int) -> NormalizedToolResult:
    """Normalize what an in-process server's ``call_tool`` returns.

    FastMCP returns content blocks, or a ``(content, structured)`` pair when
    the tool has structured output; the fake server returns plain values.
    """
    if isinstance(result, NormalizedToolResult):
        return result
    structured: Any = None
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict):
        result, structured = result
    if isinstance(result, dict):
        text = json.dumps(result, sort_keys=True, default=str)
    elif isinstance(result, list | tuple):
        text = _extract_content(result)
    else:
        text = str(result)
    return _result(_text_or_structured(text, structured), False, max_bytes)
