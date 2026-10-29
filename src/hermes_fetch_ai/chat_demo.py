"""An offline walk through a chat sale, the way an ASI:One user buys.

A buyer agent speaks the chat protocol and the payment protocol's buyer role,
as ASI:One does: it orders a service in plain text, pays the requested amount
without a memo, commits the payment, and waits for the answer. Both agents
run in this process and the ledger is simulated, so the demo needs no
network, seed, or funds.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from uagents import Context, Model, Protocol
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

from .config import BridgeConfig
from .fake_ledger import FakeLedger
from .money import parse_fet
from .registration_policies import NoopRegistrationPolicy
from .uagent_app import PrivateAgent, build_agent, build_service_desk
from .wallet import wallet_address

DEMO_SELLER_WALLET_SEED = "hermes-fetch-ai chat demo seller wallet (public, test only)"
BUYER_WALLET = "fetch1asionebuyerwalletdemo"


def chat_demo_config(state_dir: Path) -> BridgeConfig:
    return BridgeConfig.model_validate(
        {
            "agent": {"name": "hermes_chat_demo", "dev_random_seed": True},
            "payments": {
                "enabled": True,
                "payout_address": wallet_address(DEMO_SELLER_WALLET_SEED),
                "state_dir": str(state_dir),
            },
            "chat": {"enable_chat": True},
            "services": {
                "research": {
                    "title": "Research a topic",
                    "description": "Answers with your request (a demo service).",
                    "price": "0.05",
                    "runner": {"type": "echo"},
                    "disclaimer": "Demo service on Fetch's testnet; no real money involved.",
                }
            },
            "logging": {"audit_path": str(state_dir / "audit.jsonl")},
        }
    )


def asi_one_like_buyer(
    ledger: FakeLedger, received: list[Model], done: asyncio.Event
) -> PrivateAgent:
    """A buyer that orders, pays without a memo, and commits, the way ASI:One does."""
    buyer = PrivateAgent(
        name="asi_one_like_buyer",
        seed="hermes-fetch-ai chat demo buyer " + uuid.uuid4().hex,
        network="testnet",
        registration_policy=NoopRegistrationPolicy(),
        mark_inactive_on_shutdown=False,
    )
    chat = Protocol(spec=chat_protocol_spec)
    payment = Protocol(spec=payment_protocol_spec, role="buyer")

    @chat.on_message(model=ChatMessage)
    async def _chat(ctx: Context, sender: str, msg: ChatMessage) -> None:
        received.append(msg)
        await ctx.send(sender, ChatAcknowledgement(acknowledged_msg_id=msg.msg_id))
        if any(isinstance(content, EndSessionContent) for content in msg.content):
            done.set()

    @chat.on_message(model=ChatAcknowledgement)
    async def _ack(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
        received.append(msg)

    @payment.on_message(model=RequestPayment)
    async def _request(ctx: Context, sender: str, msg: RequestPayment) -> None:
        received.append(msg)
        (funds,) = msg.accepted_funds
        tx_hash = ledger.pay(
            payer=BUYER_WALLET, recipient=msg.recipient, amount_base=parse_fet(funds.amount)
        )
        await ctx.send(
            sender,
            CommitPayment(
                funds=funds,
                recipient=msg.recipient,
                transaction_id=tx_hash,
                reference=msg.reference,
                metadata={"buyer_fet_wallet": BUYER_WALLET},
            ),
        )

    @payment.on_message(model=CompletePayment)
    async def _complete(ctx: Context, sender: str, msg: CompletePayment) -> None:
        received.append(msg)

    @payment.on_message(model=CancelPayment)
    async def _cancel(ctx: Context, sender: str, msg: CancelPayment) -> None:
        received.append(msg)
        done.set()

    buyer.include(chat)
    buyer.include(payment)
    return buyer


async def run_chat_sale(
    cfg: BridgeConfig, ledger: FakeLedger, order: str, *, timeout: float = 10.0
) -> list[Model]:
    """Run one chat order through a seller and an ASI:One-like buyer; return what the buyer got."""
    seed = cfg.effective_seed()
    desk = build_service_desk(cfg, seed, ledger_factory=lambda: ledger)
    bridge = build_agent(cfg, None, seed=seed, desk=desk)
    received: list[Model] = []
    done = asyncio.Event()
    buyer = asi_one_like_buyer(ledger, received, done)
    queues = [asyncio.create_task(agent._process_message_queue()) for agent in (bridge, buyer)]
    try:
        message = ChatMessage(content=[StartSessionContent(), TextContent(text=order)])
        await dispatcher.dispatch_msg(
            sender=buyer.address,
            destination=bridge.address,
            schema_digest=Model.build_schema_digest(message),
            message=message.model_dump_json(),
            session=uuid.uuid4(),
        )
        await asyncio.wait_for(done.wait(), timeout)
    finally:
        for task in queues:
            task.cancel()
        await asyncio.gather(*queues, return_exceptions=True)
        for agent in (bridge, buyer):
            dispatcher.unregister(agent.address, agent)
        await desk.aclose()
    return received


def describe(received: list[Model], short: Callable[[str], str]) -> list[str]:
    """The buyer's side of the conversation, one line per message."""
    lines = []
    for message in received:
        if isinstance(message, ChatMessage):
            lines.append("seller says: " + message.text().replace("\n", "\n  "))
        elif isinstance(message, RequestPayment):
            (funds,) = message.accepted_funds
            lines.append(
                f"payment card: pay {funds.amount} {funds.currency} to {message.recipient} "
                f"on {message.metadata.get('fet_network') if message.metadata else '?'}"
            )
            lines.append("buyer pays, without a memo, and commits the payment")
        elif isinstance(message, CompletePayment):
            lines.append(
                f"seller confirms: payment {short(message.transaction_id or '')} verified "
                "on the ledger"
            )
        elif isinstance(message, CancelPayment):
            lines.append(f"seller cancels: {message.reason}")
    return lines


async def run_chat_demo(state_dir: Path) -> list[str]:
    from .seller import short_tx

    cfg = chat_demo_config(state_dir)
    lines = ["buyer says: research: tides in the Bay of Fundy"]
    received: list[Any] = await run_chat_sale(
        cfg, FakeLedger(), "research: tides in the Bay of Fundy"
    )
    return lines + describe(received, short_tx)
