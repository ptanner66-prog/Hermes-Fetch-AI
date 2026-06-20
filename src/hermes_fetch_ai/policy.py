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
    global_hits: dict[str, list[float]] = field(default_factory=dict)

    @staticmethod
    def _fresh(window: list[float], now: float) -> list[float]:
        return [t for t in window if now - t < 60]

    def _prune_expired(self, now: float) -> None:
        self.hits = {k: self._fresh(v, now) for k, v in self.hits.items() if self._fresh(v, now)}
        self.global_hits = {
            k: self._fresh(v, now) for k, v in self.global_hits.items() if self._fresh(v, now)
        }

    def _evict_if_needed(self, max_tracked_senders: int) -> bool:
        if max_tracked_senders <= 0:
            return False
        while len(self.hits) >= max_tracked_senders:
            oldest_key = min(
                self.hits,
                key=lambda key: self.hits[key][-1] if self.hits[key] else float("-inf"),
            )
            del self.hits[oldest_key]
        return True

    def allow(self, sender: str, kind: str, limit: int, max_tracked_senders: int = 4096) -> bool:
        if limit <= 0:
            return False
        now = time.monotonic()
        self._prune_expired(now)
        key = (sender or "unknown", kind)
        window = self._fresh(self.hits.get(key, []), now)
        if len(window) >= limit:
            self.hits[key] = window
            return False
        if key not in self.hits and not self._evict_if_needed(max_tracked_senders):
            return False
        window.append(now)
        self.hits[key] = window
        return True

    def allow_global(self, kind: str, limit: int) -> bool:
        if limit <= 0:
            return False
        now = time.monotonic()
        window = self._fresh(self.global_hits.get(kind, []), now)
        if len(window) >= limit:
            self.global_hits[kind] = window
            return False
        window.append(now)
        self.global_hits[kind] = window
        return True


@dataclass
class ReplayCache:
    entries: dict[str, float] = field(default_factory=dict)

    def _prune_expired(self, now: float, ttl_seconds: float) -> None:
        if ttl_seconds <= 0:
            self.entries.clear()
            return
        self.entries = {
            fingerprint: seen_at
            for fingerprint, seen_at in self.entries.items()
            if now - seen_at < ttl_seconds
        }

    def _evict_if_needed(self, max_entries: int) -> bool:
        if max_entries <= 0:
            return False
        while len(self.entries) >= max_entries:
            oldest = min(self.entries, key=self.entries.__getitem__)
            del self.entries[oldest]
        return True

    def allow(self, fingerprint: str, ttl_seconds: float, max_entries: int) -> tuple[bool, str]:
        if ttl_seconds <= 0:
            return True, "allowed"
        now = time.monotonic()
        self._prune_expired(now, ttl_seconds)
        if fingerprint in self.entries:
            return False, "replay detected"
        if not self._evict_if_needed(max_entries):
            return False, "replay cache full"
        self.entries[fingerprint] = now
        return True, "allowed"


BUCKETS = TokenBuckets()
REPLAYS = ReplayCache()


def consume_list_tools_rate(
    sender: str, cfg: PolicyConfig, buckets: TokenBuckets = BUCKETS
) -> tuple[bool, str]:
    if not buckets.allow_global("list_tools", cfg.max_global_list_tools_per_minute):
        return False, "global rate limit exceeded"
    if not buckets.allow(
        sender,
        "list_tools",
        cfg.max_list_tools_per_minute_per_sender,
        cfg.max_tracked_senders,
    ):
        return False, "rate limit exceeded"
    return True, "allowed"


def consume_call_rate(
    sender: str, cfg: PolicyConfig, buckets: TokenBuckets = BUCKETS
) -> tuple[bool, str]:
    if not buckets.allow_global("call_tool", cfg.max_global_calls_per_minute):
        return False, "global rate limit exceeded"
    if not buckets.allow(
        sender,
        "call_tool",
        cfg.max_calls_per_minute_per_sender,
        cfg.max_tracked_senders,
    ):
        return False, "rate limit exceeded"
    return True, "allowed"


def authorize_list_tools(
    sender: str, cfg: PolicyConfig, buckets: TokenBuckets = BUCKETS
) -> tuple[bool, str]:
    return consume_list_tools_rate(sender, cfg, buckets)


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
    *,
    consume_rate: bool = True,
) -> tuple[bool, str]:
    _ = args, protocol
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
    if consume_rate:
        ok, reason = consume_call_rate(sender, cfg, buckets)
        if not ok:
            return False, reason
    if safe_tool not in allowed:
        return False, "tool not allowed for sender"
    return True, "allowed"
