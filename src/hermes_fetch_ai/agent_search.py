"""Finding agents to talk to: Agentverse's public agent search.

Only agents that speak Fetch's chat protocol are returned, since that is how
Hermes talks to them. Everything in a result comes from the agent's own
listing, so names and descriptions are untrusted text: they are cleaned,
shortened, and labeled as such wherever they are shown.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from uagents import Protocol
from uagents_core.contrib.protocols.chat import chat_protocol_spec

SEARCH_URL = "https://agentverse.ai/v1/search/agents"
MAX_RESULTS = 20
MAX_QUERY_CHARS = 200
MAX_NAME_CHARS = 80
MAX_DESCRIPTION_CHARS = 300


class SearchError(Exception):
    """The search could not be done; the message says why, for the owner."""


@dataclass(frozen=True)
class FoundAgent:
    address: str
    name: str
    handle: str | None
    description: str
    status: str
    rating: float | None
    interactions: int
    recent_success_rate: float | None


def _clean(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    text = "".join(ch for ch in text if ch.isprintable())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _number(value: Any) -> float | None:
    try:
        return round(float(value), 3) if value is not None else None
    except (TypeError, ValueError):
        return None


def _found(entry: dict[str, Any]) -> FoundAgent | None:
    address = str(entry.get("address") or "")
    if not address.startswith("agent1") or len(address) > 100:
        return None
    readme = str(entry.get("readme") or "")
    description = entry.get("description") or next(
        (line for line in readme.splitlines() if line.strip() and not line.startswith(("#", "!"))),
        "",
    )
    handle = entry.get("handle")
    try:
        interactions = int(entry.get("total_interactions") or 0)
    except (TypeError, ValueError):
        interactions = 0
    return FoundAgent(
        address=address,
        name=_clean(entry.get("name") or "(no name)", MAX_NAME_CHARS),
        handle=_clean(handle, 40) if handle else None,
        description=_clean(description, MAX_DESCRIPTION_CHARS),
        status=_clean(entry.get("status") or "unknown", 20),
        rating=_number(entry.get("rating")),
        interactions=interactions,
        recent_success_rate=_number(entry.get("recent_success_rate")),
    )


def chat_digest() -> str:
    return str(Protocol(spec=chat_protocol_spec).digest)


def search_agents(
    query: str,
    *,
    limit: int = 10,
    api_key: str | None = None,
    timeout: float = 15.0,
    transport: httpx.BaseTransport | None = None,
) -> list[FoundAgent]:
    """Agents on Agentverse that match ``query`` and speak the chat protocol."""
    query = query.strip()
    if not query:
        raise SearchError("say what to search for")
    body = {
        "search_text": query[:MAX_QUERY_CHARS],
        "filters": {"protocol_digest": [chat_digest()]},
        "sort": "relevancy",
        "direction": "desc",
        "offset": 0,
        "limit": max(1, min(limit, MAX_RESULTS)),
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        with httpx.Client(timeout=timeout, transport=transport) as client:
            response = client.post(SEARCH_URL, json=body, headers=headers)
    except httpx.HTTPError as exc:
        raise SearchError(f"Agentverse cannot be reached: {exc}") from None
    if response.status_code != 200:
        raise SearchError(f"Agentverse answered HTTP {response.status_code}")
    try:
        agents = response.json().get("agents") or []
    except (ValueError, AttributeError):
        raise SearchError("Agentverse sent an unreadable answer") from None
    found = [_found(entry) for entry in agents if isinstance(entry, dict)]
    return [agent for agent in found if agent is not None][:MAX_RESULTS]
