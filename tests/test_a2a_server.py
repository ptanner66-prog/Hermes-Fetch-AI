import pytest

from hermes_fetch_ai.a2a_server import A2ABridge, _bearer_authorized, build_agent_card
from hermes_fetch_ai.audit import AuditWriter
from hermes_fetch_ai.config import BridgeConfig, load_config
from hermes_fetch_ai.result_normalizer import NormalizedToolResult


class FakeShim:
    def __init__(self):
        self.list_calls = 0
        self.call_calls = 0

    async def list_tools(self):
        self.list_calls += 1
        return [
            {
                "name": "echo",
                "description": "Echo text",
                "inputSchema": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            }
        ]

    async def call_tool(self, name, args):
        self.call_calls += 1
        return NormalizedToolResult(args["text"], None, False, False, len(args["text"]))


class ShimFactory:
    def __init__(self, shim):
        self.shim = shim

    def __call__(self, cfg):
        return self

    async def __aenter__(self):
        return self.shim

    async def __aexit__(self, exc_type, exc, tb):
        return False


def cfg(**policy):
    return BridgeConfig(
        agent={"dev_random_seed": True, "name": "hermes_fetch_a2a"},
        a2a={"enabled": True, "public_base_url": "https://example.test", "port": 8080},
        policy=policy,
    )


def message_send(data):
    return {
        "jsonrpc": "2.0",
        "id": "req-1",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": "msg-1",
                "parts": [{"kind": "data", "data": data}],
            },
            "metadata": {"sender": "a2a:test"},
        },
    }


def test_agent_card_is_a2a_first_and_contains_no_secret_fields():
    c = cfg(public_tools=["echo"])
    card = build_agent_card(c)
    assert card["protocolVersion"] == "0.3.0"
    assert card["preferredTransport"] == "JSONRPC"
    assert card["url"] == "https://example.test/a2a"
    assert card["metadata"]["chatProtocol"] == "out-of-scope"
    assert "secret" not in str(card).lower()
    assert "seed" not in str(card).lower()


@pytest.mark.asyncio
async def test_a2a_list_tools_empty_policy_does_not_contact_backend(tmp_path):
    shim = FakeShim()
    bridge = A2ABridge(
        cfg(public_tools=[]),
        shim_factory=ShimFactory(shim),
        audit=AuditWriter(tmp_path / "a.jsonl"),
    )
    response = await bridge.handle_jsonrpc(message_send({"operation": "list_tools"}))
    task = response["result"]
    data = task["artifacts"][0]["parts"][0]["data"]
    assert data["ok"] is True
    assert data["tools"] == []
    assert shim.list_calls == 0


@pytest.mark.asyncio
async def test_a2a_call_tool_routes_through_policy_bridge(tmp_path):
    shim = FakeShim()
    bridge = A2ABridge(
        cfg(public_tools=["echo"]),
        shim_factory=ShimFactory(shim),
        audit=AuditWriter(tmp_path / "a.jsonl"),
    )
    response = await bridge.handle_jsonrpc(
        message_send({"operation": "call_tool", "tool": "echo", "args": {"text": "hello"}})
    )
    task = response["result"]
    data = task["artifacts"][0]["parts"][0]["data"]
    assert task["status"]["state"] == "completed"
    assert data["ok"] is True
    assert data["result"] == "hello"
    assert shim.call_calls == 1


@pytest.mark.asyncio
async def test_a2a_text_chat_is_rejected_as_invalid_params(tmp_path):
    bridge = A2ABridge(
        cfg(public_tools=["echo"]),
        shim_factory=ShimFactory(FakeShim()),
        audit=AuditWriter(tmp_path / "a.jsonl"),
    )
    response = await bridge.handle_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": "req-1",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": "msg-1",
                    "parts": [{"kind": "text", "text": "hello"}],
                }
            },
        }
    )
    assert response["error"]["code"] == -32602
    assert "data part" in response["error"]["message"]


@pytest.mark.asyncio
async def test_a2a_tasks_get_returns_completed_task(tmp_path):
    bridge = A2ABridge(
        cfg(public_tools=["echo"]),
        shim_factory=ShimFactory(FakeShim()),
        audit=AuditWriter(tmp_path / "a.jsonl"),
    )
    created = await bridge.handle_jsonrpc(message_send({"operation": "list_tools"}))
    task_id = created["result"]["id"]
    fetched = await bridge.handle_jsonrpc(
        {"jsonrpc": "2.0", "id": "req-2", "method": "tasks/get", "params": {"id": task_id}}
    )
    assert fetched["result"]["id"] == task_id
    assert fetched["result"]["status"]["state"] == "completed"


def test_a2a_example_config_loads_without_runtime_seed():
    cfg = load_config("examples/a2a-local.yaml", require_runtime_secrets=False)
    assert cfg.a2a.enabled is True
    assert cfg.chat.enable_chat is False


def test_a2a_bearer_auth_uses_env_token(monkeypatch):
    monkeypatch.setenv("HERMES_FETCH_A2A_BEARER_TOKEN", "operator-token")
    c = BridgeConfig(
        agent={"dev_random_seed": True},
        a2a={"enabled": True, "require_bearer_token": True},
    )

    assert _bearer_authorized(c, "Bearer operator-token") is True
    assert _bearer_authorized(c, "Bearer wrong") is False
    assert _bearer_authorized(c, None) is False


def test_a2a_bearer_auth_fails_closed_without_env_token(monkeypatch):
    c = BridgeConfig.model_validate(
        {
            "agent": {"dev_random_seed": True},
            "a2a": {"enabled": True, "require_bearer_token": True},
        },
        context={"require_runtime_secrets": False},
    )
    monkeypatch.delenv("HERMES_FETCH_A2A_BEARER_TOKEN", raising=False)

    assert _bearer_authorized(c, "Bearer anything") is False
