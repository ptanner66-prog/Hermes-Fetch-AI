"""A chat sale between two real uAgents in one process, the way ASI:One buys.

The buyer speaks the chat protocol and the payment protocol's buyer role: it
orders a service, pays the requested amount on a fake ledger without a memo
(as ASI:One's wallet does), commits the payment, and waits for the answer.
Messages travel through uAgents' own dispatcher, so the protocol digests,
roles, and handlers are the real ones.
"""

import asyncio
import uuid

from uagents import Model, Protocol
from uagents.dispatch import dispatcher
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)
from uagents_core.contrib.protocols.payment import (
    CancelPayment,
    CommitPayment,
    CompletePayment,
    RequestPayment,
    payment_protocol_spec,
)

from hermes_fetch_ai.config import BridgeConfig
from hermes_fetch_ai.fake_ledger import FakeLedger
from hermes_fetch_ai.money import parse_fet
from hermes_fetch_ai.registration_policies import NoopRegistrationPolicy
from hermes_fetch_ai.uagent_app import PrivateAgent, build_agent, build_service_desk

PAYOUT = "fetch1hh09pm44murgmu7rpaxluwad3way3nxq0fl6fx"


def seller_config(tmp_path):
    return BridgeConfig.model_validate(
        {
            "agent": {"name": "hermes_chat_seller", "dev_random_seed": True},
            "payments": {
                "enabled": True,
                "payout_address": PAYOUT,
                "state_dir": str(tmp_path / "state"),
            },
            "chat": {"enable_chat": True},
            "services": {
                "research": {
                    "title": "Research a topic",
                    "description": "Finds sources.",
                    "price": "0.05",
                    "runner": {"type": "echo"},
                }
            },
            "logging": {"audit_path": str(tmp_path / "audit.jsonl")},
        }
    )


def asi_one_like_buyer(ledger, received, done):
    buyer = PrivateAgent(
        name="asi_one_like_buyer",
        seed="chat-flow-test-buyer-" + uuid.uuid4().hex,
        network="testnet",
        registration_policy=NoopRegistrationPolicy(),
        mark_inactive_on_shutdown=False,
    )
    chat = Protocol(spec=chat_protocol_spec)
    payment = Protocol(spec=payment_protocol_spec, role="buyer")

    @chat.on_message(model=ChatMessage)
    async def _chat(ctx, sender, msg):
        received.append(msg)
        await ctx.send(sender, ChatAcknowledgement(acknowledged_msg_id=msg.msg_id))
        if any(isinstance(c, EndSessionContent) for c in msg.content):
            done.set()

    @chat.on_message(model=ChatAcknowledgement)
    async def _ack(ctx, sender, msg):
        received.append(msg)

    @payment.on_message(model=RequestPayment)
    async def _request(ctx, sender, msg):
        received.append(msg)
        (funds,) = msg.accepted_funds
        tx_hash = ledger.pay(
            payer="fetch1asionewallet",
            recipient=msg.recipient,
            amount_base=parse_fet(funds.amount),
        )
        await ctx.send(
            sender,
            CommitPayment(
                funds=funds,
                recipient=msg.recipient,
                transaction_id=tx_hash,
                reference=msg.reference,
                metadata={"buyer_fet_wallet": "fetch1asionewallet"},
            ),
        )

    @payment.on_message(model=CompletePayment)
    async def _complete(ctx, sender, msg):
        received.append(msg)

    @payment.on_message(model=CancelPayment)
    async def _cancel(ctx, sender, msg):
        received.append(msg)
        done.set()

    buyer.include(chat)
    buyer.include(payment)
    return buyer


async def test_an_asi_one_style_buyer_orders_pays_and_gets_the_answer(tmp_path):
    cfg = seller_config(tmp_path)
    ledger = FakeLedger()
    seed = cfg.effective_seed()
    desk = build_service_desk(cfg, seed, ledger_factory=lambda: ledger)
    bridge = build_agent(cfg, object(), seed=seed, desk=desk)
    received = []
    done = asyncio.Event()
    buyer = asi_one_like_buyer(ledger, received, done)
    queues = [asyncio.create_task(agent._process_message_queue()) for agent in (bridge, buyer)]
    try:
        order = ChatMessage(content=[StartSessionContent(), TextContent(text="research: tides")])
        await dispatcher.dispatch_msg(
            sender=buyer.address,
            destination=bridge.address,
            schema_digest=Model.build_schema_digest(order),
            message=order.model_dump_json(),
            session=uuid.uuid4(),
        )
        await asyncio.wait_for(done.wait(), 10)
    finally:
        for task in queues:
            task.cancel()
        await asyncio.gather(*queues, return_exceptions=True)
        for agent in (bridge, buyer):
            dispatcher.unregister(agent.address, agent)
        await desk.aclose()

    kinds = [type(message).__name__ for message in received]
    assert kinds == [
        "ChatAcknowledgement",  # the order was acknowledged first
        "ChatMessage",  # the price
        "RequestPayment",  # ASI:One's payment card
        "CompletePayment",  # verified on the ledger
        "ChatMessage",  # the answer, ending the session
    ]
    request = received[2]
    assert request.metadata["fet_network"] == "stable-testnet"
    answer = received[-1]
    assert answer.text() == "tides"
    assert ledger.requests >= 2  # the bridge read the chain id and the transaction itself
