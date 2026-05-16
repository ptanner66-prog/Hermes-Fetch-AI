from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from .config import PolicyConfig

_TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\ufeff"}


def default_safe_public_tools() -> set[str]:
    return {"skills_list"}


def normalize_tool_name(name: str) -> str:
    """Return a canonical safe tool name or raise ValueError.

    Public tool names are policy identifiers. Rejecting aliases, control
    characters, ANSI escapes, zero-width characters, and NFKC-confusable forms
    prevents a displayed name from differing from the authorized name.
    """

    raw = str(name)
    normalized = unicodedata.normalize("NFKC", raw)
    if raw != normalized:
        raise ValueError("unsafe tool name normalization")
    if any(ch in raw for ch in _ZERO_WIDTH) or "\x1b" in raw:
        raise ValueError("unsafe tool name control character")
    if any(unicodedata.category(ch)[0] == "C" for ch in raw):
        raise ValueError("unsafe tool name control character")
    if not raw or not _TOOL_NAME_RE.fullmatch(raw):
        raise ValueError("unsafe tool name")
    return raw


def _safe_policy_names(names: list[str]) -> set[str]:
    safe: set[str] = set()
    for name in names:
        safe.add(normalize_tool_name(name))
    return safe


def _tool_name(tool: Any) -> str:
    if isinstance(tool, dict):
        return normalize_tool_name(str(tool.get("name", "")))
    return normalize_tool_name(str(getattr(tool, "name", "")))


@dataclass
class TokenBuckets:
    hits: dict[tuple[str, str], list[float]] = field(default_factory=dict)

    def allow(self, sender: str, kind: str, limit: int) -> bool:
        if limit <= 0:
            return False
        now = time.monotonic()
        key = (sender or "unknown", kind)
        window = [t for t in self.hits.get(key, []) if now - t < 60]
        if len(window) >= limit:
            self.hits[key] = window
            return False
        window.append(now)
        self.hits[key] = window
        return True


BUCKETS = TokenBuckets()


def authorize_list_tools(
    sender: str, cfg: PolicyConfig, buckets: TokenBuckets = BUCKETS
) -> tuple[bool, str]:
    if not buckets.allow(sender, "list_tools", cfg.max_list_tools_per_minute_per_sender):
        return False, "rate limit exceeded"
    return True, "allowed"


def visible_tools(sender: str, tools: list[Any], cfg: PolicyConfig) -> list[Any]:
    denied = _safe_policy_names(cfg.denied_tools)
    allowed = _safe_policy_names(cfg.allowed_senders.get(sender, []))
    public = _safe_policy_names(cfg.public_tools)
    visible = allowed | public
    out: list[Any] = []
    for tool in tools:
        try:
            name = _tool_name(tool)
        except ValueError:
            continue
        if name not in denied and name in visible:
            out.append(tool)
    return out


def authorize(
    sender: str,
    tool: str,
    args: dict[str, Any],
    protocol: str,
    cfg: PolicyConfig,
    buckets: TokenBuckets = BUCKETS,
) -> tuple[bool, str]:
    try:
        safe_tool = normalize_tool_name(tool)
        denied = _safe_policy_names(cfg.denied_tools)
        allowed = _safe_policy_names(cfg.allowed_senders.get(sender, [])) | _safe_policy_names(
            cfg.public_tools
        )
    except ValueError as exc:
        return False, str(exc)
    if safe_tool in denied:
        return False, "tool denied"
    if not buckets.allow(sender, "call_tool", cfg.max_calls_per_minute_per_sender):
        return False, "rate limit exceeded"
    if safe_tool not in allowed:
        return False, "tool not allowed for sender"
    return True, "allowed"
