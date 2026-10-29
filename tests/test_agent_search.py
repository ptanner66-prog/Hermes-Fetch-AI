"""Finding agents on Agentverse: the request sent, and how results are cleaned."""

import json

import httpx
import pytest

from hermes_fetch_ai.agent_search import (
    SEARCH_URL,
    SearchError,
    chat_digest,
    search_agents,
)

AGENT = "agent1qfuexnwkscrhfhx7tdchlz486mtzsl53grlnr3zpntxsyu6zhp2ckpemfdz"


def transport(status=200, payload=None, seen=None):
    def handle(request):
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=payload if payload is not None else {"agents": []})

    return httpx.MockTransport(handle)


def test_the_search_asks_for_agents_that_speak_chat():
    seen = []
    search_agents("research tides", limit=50, transport=transport(seen=seen))
    (request,) = seen
    assert str(request.url) == SEARCH_URL and request.method == "POST"
    body = json.loads(request.content)
    assert body["search_text"] == "research tides"
    assert body["filters"] == {"protocol_digest": [chat_digest()]}
    assert body["limit"] == 20  # at most 20
    assert "authorization" not in request.headers
    search_agents("x", api_key="av-key", transport=transport(seen=seen))
    assert seen[-1].headers["authorization"] == "Bearer av-key"


def test_results_are_cleaned_and_bad_entries_dropped():
    payload = {
        "agents": [
            {
                "address": AGENT,
                "name": "Tide\x1b[31m Research\u202e",
                "handle": "tides",
                "readme": "# Tide Research\n![badge](x)\nAnswers questions about tides.",
                "status": "active",
                "rating": "4.25",
                "total_interactions": "1200",
                "recent_success_rate": 0.91234,
            },
            {"address": "0xnotanagent", "name": "Fake"},
            {"address": AGENT, "name": "x" * 200, "description": "y" * 500, "rating": "n/a"},
            "not an object",
        ]
    }
    first, second = search_agents("tides", transport=transport(payload=payload))
    assert first.name == "Tide[31m Research"
    assert first.description == "Answers questions about tides."
    assert (first.handle, first.status, first.rating) == ("tides", "active", 4.25)
    assert (first.interactions, first.recent_success_rate) == (1200, 0.912)
    assert len(second.name) == 80 and len(second.description) == 300
    assert second.rating is None and second.status == "unknown"


@pytest.mark.parametrize(
    ("kwargs", "problem"),
    [
        ({"transport": transport(status=500)}, "HTTP 500"),
        (
            {"transport": httpx.MockTransport(lambda r: httpx.Response(200, text="<html>"))},
            "unreadable",
        ),
    ],
)
def test_search_failures_are_explained(kwargs, problem):
    with pytest.raises(SearchError, match=problem):
        search_agents("tides", **kwargs)


def test_an_unreachable_agentverse_is_explained():
    def refuse(request):
        raise httpx.ConnectError("connection refused")

    with pytest.raises(SearchError, match="cannot be reached"):
        search_agents("tides", transport=httpx.MockTransport(refuse))


def test_an_empty_search_is_refused():
    with pytest.raises(SearchError, match="say what to search for"):
        search_agents("   ", transport=transport())


def test_find_can_read_the_search_from_standard_input(monkeypatch, capsys):
    import io

    from hermes_fetch_ai import agent_search, cli

    asked = []

    def search(query, *, limit, api_key):
        asked.append((query, limit))
        return []

    monkeypatch.setattr(agent_search, "search_agents", search)
    stdin = io.TextIOWrapper(io.BytesIO(b"tide research & more\r\n"))
    monkeypatch.setattr("sys.stdin", stdin)
    assert cli.main(["buyer", "find", "-", "--limit", "3", "--json"]) == 0
    assert asked == [("tide research & more", 3)]
    assert json.loads(capsys.readouterr().out) == []
    assert cli.main(["buyer", "find", "tides"]) == 0
    assert asked[-1] == ("tides", 10) and "no agents found" in capsys.readouterr().out
