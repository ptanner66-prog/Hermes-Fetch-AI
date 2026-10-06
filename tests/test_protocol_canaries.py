"""Canaries: Fetch's protocols, as the installed uAgents defines them.

Other agents and ASI:One find the bridge by these protocol digests, and
ASI:One's payment card reads these message fields. An upgrade of uAgents (or
uagents-core, or the MCP adapter) that changed any of them would change what
the bridge says on the wire. These tests make that fail here, by name, rather
than as a silent mismatch with agents that still speak the old version.
"""

import pytest
from uagents import Protocol
from uagents.dispatch import dispatcher
from uagents_adapter.mcp.protocol import mcp_protocol_spec
from uagents_core.contrib.protocols import chat, payment

from hermes_fetch_ai import agentverse
from hermes_fetch_ai.agent_search import chat_digest
from hermes_fetch_ai.buy_demo import buy_demo_config
from hermes_fetch_ai.chat_demo import chat_demo_config
from hermes_fetch_ai.config import BridgeConfig
from hermes_fetch_ai.store import Store
from hermes_fetch_ai.uagent_app import (
    build_agent,
    build_buyer,
    build_service_desk,
    payment_store_path,
)

# AgentChatProtocol 0.3.0, the chat protocol ASI:One speaks.
CHAT = "proto:30a801ed3a83f9a0ff0a9f1e6fe958cb91da1fc2218b153df7b6cbf87bd33d62"
# AgentPaymentProtocol 0.1.0, in each role, and Fetch's MCP message models as a server.
PAYMENT_SELLER = "proto:74bbe17d083d81bf3afb28af299aa285d3bf800ac264775923cdd3cb7b47d069"
PAYMENT_BUYER = "proto:0a80568ab5e6efbe55d6e5cf44ce879c061830f58c446772487cf91620b67c02"
MCP_SERVER = "proto:bc7aed33dbd44a2a415c513666b6f2504ba7ab63ba326dbe63efd86921c629dc"


def fields(model: type) -> list[str]:
    return list(model.__fields__)  # type: ignore[attr-defined]


def test_protocol_versions_and_digests():
    spec = chat.chat_protocol_spec
    assert (spec.name, spec.version) == ("AgentChatProtocol", "0.3.0")
    spec = payment.payment_protocol_spec
    assert (spec.name, spec.version) == ("AgentPaymentProtocol", "0.1.0")
    assert (mcp_protocol_spec.name, mcp_protocol_spec.version) == ("MCPProtocol", "0.1.0")
    assert Protocol(spec=chat.chat_protocol_spec).digest == CHAT == chat_digest()
    assert Protocol(spec=payment.payment_protocol_spec, role="seller").digest == PAYMENT_SELLER
    assert Protocol(spec=payment.payment_protocol_spec, role="buyer").digest == PAYMENT_BUYER
    assert Protocol(spec=mcp_protocol_spec, role="server").digest == MCP_SERVER


def test_payment_messages_have_the_fields_the_bridge_and_asi_one_use():
    # RequestPayment is what ASI:One draws its payment card from; CommitPayment carries
    # the buyer's transaction back.
    assert fields(payment.Funds) == ["amount", "currency", "payment_method"]
    assert fields(payment.RequestPayment) == [
        "accepted_funds",
        "recipient",
        "deadline_seconds",
        "reference",
        "description",
        "metadata",
    ]
    assert fields(payment.CommitPayment) == [
        "funds",
        "recipient",
        "transaction_id",
        "reference",
        "description",
        "metadata",
    ]
    assert fields(payment.CompletePayment) == ["transaction_id"]
    assert fields(payment.CancelPayment) == ["transaction_id", "reason"]
    assert fields(payment.RejectPayment) == ["reason"]


def test_chat_messages_have_the_fields_the_bridge_uses():
    assert fields(chat.ChatMessage) == ["timestamp", "msg_id", "content"]
    assert fields(chat.ChatAcknowledgement) == ["timestamp", "acknowledged_msg_id", "metadata"]
    assert fields(chat.TextContent) == ["type", "text"]
    assert fields(chat.StartSessionContent) == ["type"]
    assert fields(chat.EndSessionContent) == ["type"]


def variant(cfg: BridgeConfig, **sections: dict[str, object]) -> BridgeConfig:
    data = cfg.model_dump()
    for section, values in sections.items():
        data[section] = {**data[section], **values}
    return BridgeConfig.model_validate(data)


async def spoken(cfg: BridgeConfig) -> set[str]:
    """The protocols an agent built from ``cfg`` speaks, assembled the way ``serve`` does."""
    seed = cfg.effective_seed()
    store = (
        Store.open(payment_store_path(cfg, seed))
        if cfg.payments.enabled or cfg.buying.enabled
        else None
    )
    desk = build_service_desk(cfg, seed, store=store) if cfg.payments.enabled else None
    buyer = build_buyer(cfg, seed, store) if store is not None and cfg.buying.enabled else None
    agent = build_agent(cfg, None, seed=seed, desk=desk, buyer=buyer)
    try:
        return set(agent.protocols)
    finally:
        dispatcher.unregister(agent.address, agent)
        if buyer is not None:
            await buyer.aclose()
        if desk is not None:
            await desk.aclose()
        if store is not None:
            store.close()


@pytest.mark.asyncio
async def test_what_the_bridge_lists_on_agentverse_is_what_it_speaks(tmp_path, monkeypatch):
    monkeypatch.setenv("UAGENT_SEED", "protocol-canary-" + "s" * 40)  # buying needs a stable key
    stable = {"dev_random_seed": False}
    chat_seller = chat_demo_config(tmp_path / "chat-seller")
    buyer = variant(buy_demo_config(tmp_path / "buyer"), agent=stable, buying={"enabled": True})
    # Sells over MCP calls only, and buys: no chat orders, so no seller role in chat.
    mcp_seller_buyer = variant(
        chat_demo_config(tmp_path / "mcp-seller"),
        agent=stable,
        chat={"enable_chat": False},
        buying={"enabled": True},
    )
    mcp_seller = variant(chat_demo_config(tmp_path / "mcp-only"), chat={"enable_chat": False})
    cases = [
        (chat_seller, {CHAT, PAYMENT_SELLER, MCP_SERVER}),
        (buyer, {CHAT, PAYMENT_BUYER, MCP_SERVER}),
        (mcp_seller_buyer, {CHAT, PAYMENT_BUYER, MCP_SERVER}),
        (mcp_seller, {MCP_SERVER}),
    ]
    for cfg, expected in cases:
        assert await spoken(cfg) == expected
        assert set(agentverse.protocol_digests(cfg)) == expected
    # Only an agent that takes orders through chat invites ASI:One users to order.
    assert "## How to order" in agentverse.readme(chat_seller)
    assert "## How to order" not in agentverse.readme(mcp_seller_buyer)
    assert "it sells nothing here" in agentverse.readme(mcp_seller_buyer)
