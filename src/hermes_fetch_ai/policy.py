from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .config import PolicyConfig
from .tool_names import validate_tool_name

_WINDOW_SECONDS = 60.0


def _clock() -> float:
    return time.monotonic()


@dataclass
class TokenBuckets:
    """Sliding one-minute windows of request times, per sender and overall."""

    hits: dict[tuple[str, str], list[float]] = field(default_factory=dict)
    global_hits: dict[str, list[float]] = field(default_factory=dict)

    @staticmethod
    def _fresh(window: list[float], now: float) -> list[float]:
        return [t for t in window if now - t < _WINDOW_SECONDS]

    def _prune_expired(self, now: float) -> None:
        self.hits = {k: w for k, v in self.hits.items() if (w := self._fresh(v, now))}
        self.global_hits = {k: w for k, v in self.global_hits.items() if (w := self._fresh(v, now))}

    def _evict_least_recent(self, max_tracked_senders: int) -> None:
        while len(self.hits) >= max_tracked_senders:
            oldest = min(self.hits, key=lambda key: self.hits[key][-1])
            del self.hits[oldest]

    def consume(
        self,
        sender: str,
        kind: str,
        per_sender_limit: int,
        global_limit: int,
        max_tracked_senders: int,
    ) -> tuple[bool, str]:
        """Count one request against the sender's and the global limit.

        The sender's limit is checked first and a request only counts once it
        passes both checks, so one sender's rejected requests cannot use up the
        global budget and lock everyone else out.
        """
        now = _clock()
        self._prune_expired(now)
        key = (sender or "unknown", kind)
        window = self.hits.get(key, [])
        if len(window) >= per_sender_limit:
            return False, "rate limit exceeded"
        global_window = self.global_hits.get(kind, [])
        if len(global_window) >= global_limit:
            return False, "global rate limit exceeded"
        if key not in self.hits:
            self._evict_least_recent(max_tracked_senders)
        self.hits[key] = [*window, now]
        self.global_hits[kind] = [*global_window, now]
        return True, "allowed"


@dataclass
class ReplayCache:
    """Fingerprints of accepted calls, remembered while a replay could still be fresh."""

    entries: dict[str, float] = field(default_factory=dict)

    def remember(
        self, fingerprint: str, retention_seconds: float, max_entries: int
    ) -> tuple[bool, str]:
        """Record ``fingerprint``, or report it as a replay if it is already known."""
        now = _clock()
        self.entries = {
            known: seen_at
            for known, seen_at in self.entries.items()
            if now - seen_at < retention_seconds
        }
        if fingerprint in self.entries:
            return False, "replay detected"
        while len(self.entries) >= max_entries:
            del self.entries[min(self.entries, key=self.entries.__getitem__)]
        self.entries[fingerprint] = now
        return True, "allowed"


@dataclass
class PolicyState:
    """Rate-limit and replay state for one bridge."""

    buckets: TokenBuckets = field(default_factory=TokenBuckets)
    replays: ReplayCache = field(default_factory=ReplayCache)


def replay_retention_seconds(cfg: PolicyConfig) -> float:
    """How long a call's fingerprint must be remembered.

    A call is fresh from ``max_replay_clock_skew_seconds`` before its issue time
    until ``replay_ttl_seconds`` after it, so a copy of it can arrive up to
    ``ttl + skew`` after the original. One extra second covers rounding at the
    boundary.
    """
    return cfg.replay_ttl_seconds + cfg.max_replay_clock_skew_seconds + 1.0


def consume_list_tools_rate(sender: str, cfg: PolicyConfig, state: PolicyState) -> tuple[bool, str]:
    return state.buckets.consume(
        sender,
        "list_tools",
        cfg.max_list_tools_per_minute_per_sender,
        cfg.max_global_list_tools_per_minute,
        cfg.max_tracked_senders,
    )


def consume_call_rate(sender: str, cfg: PolicyConfig, state: PolicyState) -> tuple[bool, str]:
    return state.buckets.consume(
        sender,
        "call_tool",
        cfg.max_calls_per_minute_per_sender,
        cfg.max_global_calls_per_minute,
        cfg.max_tracked_senders,
    )


def _tool_name(tool: Any) -> str:
    raw = tool.get("name", "") if isinstance(tool, dict) else getattr(tool, "name", "")
    return validate_tool_name(str(raw))


def visible_tools(sender: str, tools: list[Any], cfg: PolicyConfig) -> list[Any]:
    """The tools ``sender`` may see: public or allowlisted for them, and not denied."""
    visible = set(cfg.public_tools) | set(cfg.allowed_senders.get(sender, []))
    out: list[Any] = []
    for tool in tools:
        try:
            name = _tool_name(tool)
        except ValueError:
            continue
        if name in visible and name not in cfg.denied_tools:
            out.append(tool)
    return out


def authorize(sender: str, tool: str, cfg: PolicyConfig) -> tuple[bool, str]:
    """Default deny: ``tool`` must be public or allowlisted for ``sender``, and not denied."""
    if tool in cfg.denied_tools:
        return False, "tool denied"
    if tool not in cfg.public_tools and tool not in cfg.allowed_senders.get(sender, []):
        return False, "tool not allowed for sender"
    return True, "allowed"
