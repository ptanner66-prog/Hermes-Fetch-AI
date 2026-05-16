import pytest
from uagents import Agent, Protocol
from uagents.dispatch import dispatcher
from uagents_adapter.mcp.protocol import CallTool, mcp_protocol_spec

from hermes_fetch_ai.audit import AuditWriter
from hermes_fetch_ai.config import BridgeConfig
from hermes_fetch_ai.direct_protocol import build_protocol
from hermes_fetch_ai.mcp_shim import HermesMCPClientShim
from hermes_fetch_ai.registration_policies import NoopRegistrationPolicy
from hermes_fetch_ai.uagent_app import build_agent, local_dispatch_request


def cfg():
    return BridgeConfig(agent={"dev_random_seed": True}, policy={"public_tools": ["echo"]})


def test_noop_registration_policy_noops():
    assert NoopRegistrationPolicy().should_register() is False


@pytest.mark.asyncio
async def test_noop_registration_policy_register_noops():
    assert await NoopRegistrationPolicy().register("id", None, [], [], None) is None


def test_build_agent_wires_noop_registration_policy_when_not_publishing(monkeypatch):
    captured = {}

    class FakeAgent:
        address = "agent1qfake"

        def __init__(self, **kwargs):
            captured.update(kwargs)

        def include(self, protocol, publish_manifest=False):
            captured["included_protocol"] = protocol
            captured["include_publish_manifest"] = publish_manifest

    monkeypatch.setattr("hermes_fetch_ai.uagent_app.Agent", FakeAgent)
    c = cfg()
    build_agent(c, object())
    assert isinstance(captured["registration_policy"], NoopRegistrationPolicy)
    assert captured["network"] == "testnet"
    assert captured["enable_agent_inspector"] is False
    assert captured["publish_agent_details"] is False
    assert captured["include_publish_manifest"] is False


def test_protocol_signed_handlers_and_no_adapter_or_chat():
    c = cfg()
    proto = build_protocol(object(), c, AuditWriter(c.audit_path))
    assert isinstance(proto, Protocol)
    assert proto._spec == mcp_protocol_spec
    assert proto.unsigned_message_handlers == {}
    assert "chat" not in repr(proto).lower()
    assert "MCPServerAdapter" not in repr(proto)


def test_exactly_one_bridge_protocol_shape():
    c = cfg()
    proto = build_protocol(object(), c, AuditWriter(c.audit_path))
    assert proto._spec.name == "MCPProtocol"


@pytest.mark.asyncio
async def test_client_list_and_call_succeeds_via_local_dispatcher(tmp_path, monkeypatch):
    dispatched = {"count": 0}
    original_dispatch = dispatcher.dispatch_msg

    async def spy_dispatch(*args, **kwargs):
        dispatched["count"] += 1
        return await original_dispatch(*args, **kwargs)

    monkeypatch.setattr(dispatcher, "dispatch_msg", spy_dispatch)
    c = cfg()
    c.logging.audit_path = str(tmp_path / "a.jsonl")
    async with HermesMCPClientShim(c) as shim:
        bridge = build_agent(c, shim)
        client = Agent(
            name="client",
            seed="client-seed-for-local-dispatch-test",
            network="testnet",
            registration_policy=NoopRegistrationPolicy(),
            enable_agent_inspector=False,
            publish_agent_details=False,
        )
        try:
            tools = await local_dispatch_request(
                bridge,
                client,
                __import__("uagents_adapter.mcp.protocol", fromlist=["ListTools"]).ListTools(),
                __import__("uagents_adapter.mcp.protocol", fromlist=["ListToolsResponse"]).ListToolsResponse,
            )
            result = await local_dispatch_request(
                bridge,
                client,
                CallTool(tool="echo", args={"text": "hello"}),
                __import__("uagents_adapter.mcp.protocol", fromlist=["CallToolResponse"]).CallToolResponse,
            )
        finally:
            dispatcher.unregister(bridge.address, bridge)
            dispatcher.unregister(client.address, client)
    assert tools.tools and result.result == "hello"
    assert dispatched["count"] >= 4
