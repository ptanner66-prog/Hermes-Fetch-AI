"""Field test: the guest Hermes runner against a real hermes-agent install.

Skipped unless both env vars are set (see tests/test_field_hermes_stdio.py for
the one-time setup):

  HERMES_FETCH_FIELD_TEST=1
  HERMES_FETCH_HERMES_PYTHON=/path/to/hermes-venv/bin/python

The model is a scripted stand-in on 127.0.0.1 (tests/fakes/fake_model_server.py),
so no account or key is needed. It checks what Hermes itself offered the model
and did with its answers: only the service's tools, a refused terminal call, a
refused private URL, and nothing left behind. CI runs this against Hermes
0.21.5 and a pinned main.
"""

import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from hermes_fetch_ai.config import BridgeConfig
from hermes_fetch_ai.guest import HermesRunner, guest_problems
from hermes_fetch_ai.services import build_runner

from .fakes.fake_model_server import FakeModelServer, text_reply, tool_reply

pytestmark = pytest.mark.skipif(
    os.environ.get("HERMES_FETCH_FIELD_TEST") != "1"
    or not os.environ.get("HERMES_FETCH_HERMES_PYTHON"),
    reason="field test requires HERMES_FETCH_FIELD_TEST=1 and HERMES_FETCH_HERMES_PYTHON",
)

PAYOUT = "fetch1hh09pm44murgmu7rpaxluwad3way3nxq0fl6fx"


def guest_cfg(tmp_path, server, **runner):
    return BridgeConfig.model_validate(
        {
            "agent": {"dev_random_seed": True},
            "payments": {
                "enabled": True,
                "payout_address": PAYOUT,
                "state_dir": str(tmp_path / "state"),
            },
            "services": {
                "research": {
                    "title": "Research a topic",
                    "description": "Finds and summarizes sources.",
                    "price": "0.05",
                    "runner": {
                        "type": "hermes",
                        "model": "fake-model",
                        "provider": "custom",
                        "base_url": server.base_url,
                        "python": os.environ["HERMES_FETCH_HERMES_PYTHON"],
                        "timeout_seconds": 240,
                        **runner,
                    },
                }
            },
        }
    )


async def run(config, request):
    runner = build_runner(config, "research")
    assert isinstance(runner, HermesRunner)
    return await runner.run(request)


def tool_results(server):
    return [
        str(message.get("content"))
        for request in server.requests
        for message in request.get("messages", [])
        if message.get("role") == "tool"
    ]


async def test_a_research_guest_gets_only_the_web_tools(tmp_path):
    marker = tmp_path / "terminal-ran"
    replies = [
        tool_reply("terminal", {"command": f"touch {marker}"}),
        text_reply("Tides come from the moon's pull."),
    ]
    with FakeModelServer(replies) as server:
        config = guest_cfg(tmp_path, server, toolsets=["web"])
        assert guest_problems(config, "research") == []
        result = await run(config, "What causes tides?")
    assert result.ok, result.problem
    assert result.text == "Tides come from the moon's pull."
    assert server.offered_tools() == {"web_search", "web_extract"}
    (refusal,) = tool_results(server)
    assert "terminal" in refusal and "does not exist" in refusal
    assert not marker.exists()
    # The run's model calls only: no session title, no background review.
    assert len(server.requests) == 2
    assert not (tmp_path / "state").exists()  # the guest kept nothing


# What ASI:One's chat completions accept (https://docs.asi1.ai/openapi.json); it answers any
# other top-level field with 400 unknown_parameter.
ASI_ONE_CHAT_FIELDS = frozenset(
    {
        "agents",
        "enable_thinking",
        "max_tokens",
        "messages",
        "model",
        "parallel_tool_calls",
        "planner_mode",
        "response_format",
        "stop",
        "stream",
        "temperature",
        "thinking_budget",
        "tool_choice",
        "tools",
        "top_p",
    }
)


async def test_a_guest_works_with_an_endpoint_as_strict_as_asi_one(tmp_path):
    # Research can run on ASI:One's model. Hermes adds fields ASI:One does not know
    # (stream_options, reasoning_effort); it must drop them when told, and the key that
    # key_env names must reach the endpoint.
    keys = tmp_path / "research.env"
    keys.write_text("ASI_ONE_API_KEY=asi-test-key\n")
    keys.chmod(0o600)
    replies = [tool_reply("web_search", {"query": "tides"}), text_reply("Tides follow the moon.")]
    with FakeModelServer(replies, accepted_fields=ASI_ONE_CHAT_FIELDS) as server:
        config = guest_cfg(
            tmp_path, server, toolsets=["web"], key_env="ASI_ONE_API_KEY", env_file=str(keys)
        )
        assert guest_problems(config, "research") == []
        result = await run(config, "What causes tides?")
    assert result.ok, result.problem
    assert result.text == "Tides follow the moon."
    assert server.requests  # answered after the refusals, if Hermes still sends such fields
    assert set(server.authorizations) == {"Bearer asi-test-key"}


async def test_a_guest_without_toolsets_gets_no_tools(tmp_path):
    with FakeModelServer([text_reply("A review of your code.")]) as server:
        result = await run(guest_cfg(tmp_path, server), "def f(): pass")
    assert result.ok and result.text == "A review of your code."
    assert server.offered_tools() == set()
    assert len(server.requests) == 1


async def test_a_guest_cannot_fetch_private_addresses(tmp_path):
    hits = []

    class Secret(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            hits.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"the owner's private page")

    secret = ThreadingHTTPServer(("127.0.0.1", 0), Secret)
    threading.Thread(target=secret.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{secret.server_port}/admin"
    try:
        replies = [tool_reply("web_extract", {"urls": [url]}), text_reply("I could not read it.")]
        with FakeModelServer(replies) as server:
            result = await run(guest_cfg(tmp_path, server, toolsets=["web"]), f"Summarize {url}")
    finally:
        secret.shutdown()
        secret.server_close()
    assert result.ok and result.text == "I could not read it."
    (blocked,) = tool_results(server)
    assert "private or internal network address" in blocked
    assert hits == []
