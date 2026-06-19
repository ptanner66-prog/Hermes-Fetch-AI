from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class NormalizedToolResult:
    text: str
    structured: dict[str, Any] | None
    is_error: bool
    truncated: bool
    output_bytes: int


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


def _extract_content(content: Any) -> str:
    blocks = content if isinstance(content, list) else [content]
    parts: list[str] = []
    for block in blocks:
        typ = getattr(block, "type", None) or (
            block.get("type") if isinstance(block, dict) else None
        )
        if typ == "text" or hasattr(block, "text") or (isinstance(block, dict) and "text" in block):
            parts.append(str(getattr(block, "text", None) or block.get("text")))
        elif typ in {"image", "audio", "resource"}:
            parts.append(f"[{typ} content omitted]")
        elif block is not None:
            parts.append(str(block))
    return "\n".join(parts)


def from_call_tool_result(result: Any, max_bytes: int) -> NormalizedToolResult:
    structured = getattr(result, "structuredContent", None) or getattr(
        result, "structured_content", None
    )
    if structured is None and isinstance(result, dict):
        structured = result.get("structuredContent") or result.get("structured")
    content = (
        getattr(result, "content", None) if not isinstance(result, dict) else result.get("content")
    )
    text = _extract_content(content)
    if not text and structured is not None:
        text = json.dumps(structured, sort_keys=True)
    is_error = bool(
        getattr(result, "isError", False)
        or getattr(result, "is_error", False)
        or (isinstance(result, dict) and result.get("isError", False))
    )
    capped, truncated, original = _cap(text, max_bytes)
    return NormalizedToolResult(capped, structured, is_error, truncated, original)


def from_fastmcp_result(result: Any, max_bytes: int) -> NormalizedToolResult:
    if isinstance(result, NormalizedToolResult):
        return result
    if isinstance(result, dict):
        text = json.dumps(result, sort_keys=True)
        structured = result
    else:
        text = str(result)
        structured = None
    capped, truncated, original = _cap(text, max_bytes)
    return NormalizedToolResult(capped, structured, False, truncated, original)
