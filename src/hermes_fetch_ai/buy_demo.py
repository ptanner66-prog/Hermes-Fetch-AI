"""An offline walk through Hermes buying from another agent.

Two bridges run in this process: one sells a research service through chat
(as in ``demo chat``), the other buys it the way Hermes does, through the
same calls Hermes' plugin makes. Messages travel through uAgents' own
dispatcher, so the protocols, roles, and sessions are the real ones; only the
ledger is simulated, so the demo needs no network, seed, or funds.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from pathlib import Path

from uagents.dispatch import dispatcher

from .buyer import Buyer
from .chat_demo import chat_demo_config
from .config import BridgeConfig
from .fake_ledger import FakeLedger, FakeSender
from .money import format_fet
from .store import InboxEntry, Purchase, Store
from .uagent_app import build_agent, build_buyer, build_service_desk, payment_store_path
from .wallet import BUYING_WALLET_INDEX, wallet_address


def buy_demo_config(state_dir: Path) -> BridgeConfig:
    return BridgeConfig.model_validate(
        {
            "agent": {"name": "hermes_buyer_demo", "dev_random_seed": True},
            "payments": {"state_dir": str(state_dir)},
            "logging": {"audit_path": str(state_dir / "audit.jsonl")},
        }
    )


async def _until(
    buyer: Buyer,
    peer: str,
    session: str,
    after_id: int,
    done: Callable[[list[InboxEntry]], bool],
    timeout: float,
) -> list[InboxEntry]:
    """Collect replies in a conversation until ``done`` says so."""
    seen: list[InboxEntry] = []
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not done(seen):
        left = deadline - loop.time()
        if left <= 0:
            raise TimeoutError("the other agent stopped answering")
        # `done` decides when the conversation is complete, so take replies as they come.
        new = await buyer.wait_for_reply(peer, session, after_id=after_id, timeout=left, settle=0.0)
        if new:
            seen += new
            after_id = new[-1].id
    return seen


async def run_purchase(
    state_dir: Path, ledger: FakeLedger, request: str, *, timeout: float = 10.0
) -> tuple[list[InboxEntry], Purchase]:
    """Hermes asks a selling bridge for ``request`` and pays; returns the replies and purchase."""
    seller_cfg = chat_demo_config(state_dir / "seller")
    seller_seed = seller_cfg.effective_seed()
    desk = build_service_desk(seller_cfg, seller_seed, ledger_factory=lambda: ledger)
    seller = build_agent(seller_cfg, None, seed=seller_seed, desk=desk)

    buyer_cfg = buy_demo_config(state_dir / "buyer")
    buyer_seed = buyer_cfg.effective_seed()
    store = Store.open(payment_store_path(buyer_cfg, buyer_seed))
    sender = FakeSender(ledger, wallet_address(buyer_seed, BUYING_WALLET_INDEX))
    buyer = build_buyer(buyer_cfg, buyer_seed, store, sender=sender, ledger_factory=lambda: ledger)
    buying_agent = build_agent(buyer_cfg, None, seed=buyer_seed, buyer=buyer)

    agents = (seller, buying_agent)
    queues = [asyncio.create_task(agent._process_message_queue()) for agent in agents]
    try:
        session, mark = await buyer.message(seller.address, request)
        replies = await _until(
            buyer,
            seller.address,
            session,
            mark,
            lambda seen: any(e.kind == "payment_request" for e in seen),
            timeout,
        )
        (asked,) = store.open_quotes(seller.address, session)
        # What the owner approves in Hermes: this exact request, as shown.
        shown = buyer.show(asked.id)
        assert shown.nonce is not None
        purchase = await buyer.pay(
            shown.id,
            nonce=shown.nonce,
            expect_amount_base=shown.amount_base,
            expect_recipient=shown.recipient,
        )
        replies += await _until(
            buyer,
            seller.address,
            session,
            replies[-1].id,
            lambda seen: any(e.kind == "end" for e in seen),
            timeout,
        )
        final = store.purchase(purchase.id)
        assert final is not None
        return replies, final
    finally:
        for task in queues:
            task.cancel()
        await asyncio.gather(*queues, return_exceptions=True)
        for agent in agents:
            dispatcher.unregister(agent.address, agent)
        await buyer.aclose()
        await desk.aclose()
        with contextlib.suppress(Exception):
            store.close()


def describe(replies: list[InboxEntry], purchase: Purchase) -> list[str]:
    lines = []
    for entry in replies:
        if entry.kind == "text":
            lines.append("seller says: " + entry.body.replace("\n", "\n  "))
        elif entry.kind == "payment_request":
            lines.append("payment request: " + entry.body.split(": ", 1)[0])
            lines.append(
                f"owner approves: pay {format_fet(purchase.amount_base)} testnet FET to "
                f"{purchase.recipient}"
            )
        elif entry.kind == "payment_complete":
            lines.append(f"seller confirms: {entry.body}")
    lines.append(f"purchase {purchase.id}: {purchase.status}")
    return lines


async def run_buy_demo(state_dir: Path) -> list[str]:
    request = "research: tides in the Bay of Fundy"
    replies, purchase = await run_purchase(state_dir, FakeLedger(), request)
    return [f"hermes says: {request}", *describe(replies, purchase)]
