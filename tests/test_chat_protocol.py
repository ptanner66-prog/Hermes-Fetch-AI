"""Selling through chat: what an ASI:One user sees, with a fake context and ledger."""

import asyncio
import dataclasses
import time
import uuid

import pytest
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
)
from uagents_core.contrib.protocols.payment import (
    CancelPayment,
    CommitPayment,
    CompletePayment,
    Funds,
    RejectPayment,
    RequestPayment,
)

from hermes_fetch_ai.audit import AuditWriter
from hermes_fetch_ai.chat_protocol import (
    PENDING_RETRY_DELAYS,
    ChatDesk,
    Order,
    OrderBook,
    chat_digest,
    sentence,
)
from hermes_fetch_ai.config import BridgeConfig
from hermes_fetch_ai.fake_ledger import FakeLedger
from hermes_fetch_ai.money import parse_fet
from hermes_fetch_ai.programs import ServiceResult
from hermes_fetch_ai.quotes import quote_key
from hermes_fetch_ai.seller import ORDER_CODE_UNIT, Seller
from hermes_fetch_ai.services import ServiceDesk
from hermes_fetch_ai.store import Store

PAYOUT = "fetch1hh09pm44murgmu7rpaxluwad3way3nxq0fl6fx"
BUYER = "agent1qbuyerbuyerbuyerbuyerbuyerbuyerbuyerbuyerbuyerbuyerbuyer"
THIEF = "agent1qthiefthiefthiefthiefthiefthiefthiefthiefthiefthiefthief"
KEY = quote_key("only for these tests, at least thirty-two characters")


class Context:
    """The part of a uAgents context the chat desk uses: the session and send()."""

    def __init__(self, session=None):
        self.session = session or uuid.uuid4()
        self.sent = []

    async def send(self, destination, message):
        self.sent.append((destination, message))

    def take(self):
        sent, self.sent = self.sent, []
        return sent


def text_of(message):
    return "".join(c.text for c in message.content if isinstance(c, TextContent))


def ends_session(message):
    return any(isinstance(c, EndSessionContent) for c in message.content)


def config(**services_override):
    services = {
        "research": {
            "title": "Research a topic",
            "description": "Finds sources.",
            "price": "0.05",
            "runner": {"type": "echo"},
            "disclaimer": "Check the sources yourself.",
        },
        "free": {"title": "Free echo", "description": "Echoes.", "runner": {"type": "echo"}},
    }
    services.update(services_override)
    return BridgeConfig.model_validate(
        {
            "agent": {"name": "hermes_seller", "dev_random_seed": True},
            "payments": {"enabled": True, "payout_address": PAYOUT},
            "chat": {"enable_chat": True},
            "services": services,
        }
    )


class Shop:
    """A chat desk with its store, ledger, and a fast clock for payment retries."""

    def __init__(self, tmp_path, cfg=None, runners=None):
        self.cfg = cfg or config()
        self.ledger = FakeLedger()
        self.store_path = tmp_path / "payments.sqlite3"
        self.audit = AuditWriter(tmp_path / "audit.jsonl")
        self.runners = runners
        self.sleeps = []
        self.open()

    def open(self):
        seller = Seller(
            payments=self.cfg.payments,
            store=Store.open(self.store_path),
            key=KEY,
            payout=PAYOUT,
            ledger_factory=lambda: self.ledger,
        )
        self.desk = ServiceDesk(self.cfg, seller, self.runners)

        async def sleep(seconds):
            self.sleeps.append(seconds)

        self.chat = ChatDesk(self.cfg, self.desk, self.audit, sleep=sleep)

    def restart(self):
        self.close()
        self.open()

    def close(self):
        self.desk.seller.store.close()

    async def say(self, text, ctx=None, sender=BUYER):
        ctx = ctx or Context()
        msg = ChatMessage(content=[TextContent(text=text)])
        await self.chat.on_chat(ctx, sender, msg)
        sent = ctx.take()
        (to, ack), *rest = sent
        assert (to, type(ack), ack.acknowledged_msg_id) == (sender, ChatAcknowledgement, msg.msg_id)
        return rest

    def pay(self, request, *, amount=None, memo=""):
        return self.ledger.pay(
            payer="fetch1buyerwallet",
            recipient=request.recipient,
            amount_base=parse_fet(request.accepted_funds[0].amount) if amount is None else amount,
            memo=memo,
        )

    async def commit(self, request, tx_hash, ctx=None, sender=BUYER, reference=True):
        ctx = ctx or Context()
        msg = CommitPayment(
            funds=request.accepted_funds[0],
            recipient=request.recipient,
            transaction_id=tx_hash,
            reference=request.reference if reference else None,
            metadata={"buyer_fet_wallet": "fetch1buyerwallet"},
        )
        await self.chat.on_commit(ctx, sender, msg)
        return ctx.take()


@pytest.fixture
def shop(tmp_path):
    s = Shop(tmp_path)
    yield s
    s.close()


async def order(shop, text="research: tides", ctx=None, sender=BUYER):
    """Order a paid service and return the RequestPayment."""
    replies = await shop.say(text, ctx=ctx, sender=sender)
    (_, intro), (to, request) = replies
    assert to == sender and isinstance(request, RequestPayment)
    assert "costs 0.05 testnet FET" in text_of(intro)
    return request


async def test_any_other_message_gets_the_menu(shop):
    ((to, reply),) = await shop.say("hello")
    assert to == BUYER and "I'm hermes_seller, a Hermes agent" in text_of(reply)
    assert "**Research a topic** (`research`), 0.05 testnet FET" in text_of(reply)
    assert not ends_session(reply)


async def test_a_service_named_without_a_request_explains_how_to_order(shop):
    ((_, reply),) = await shop.say("research")
    assert "`research: <your request>`" in text_of(reply)


async def test_a_free_service_answers_at_once(shop):
    ((_, reply),) = await shop.say("free: hi there")
    assert text_of(reply) == "hi there" and ends_session(reply)


async def test_a_paid_order_asks_for_payment_in_the_shape_asi_one_shows(shop):
    request = await order(shop)
    (funds,) = request.accepted_funds
    assert (funds.currency, funds.payment_method) == ("FET", "fet_direct")
    amount = parse_fet(funds.amount)
    code, rest = divmod(amount - parse_fet("0.05"), ORDER_CODE_UNIT)
    assert rest == 0 and 1 <= code < 2**16  # the price plus this order's code
    assert request.recipient == PAYOUT
    assert request.deadline_seconds == shop.cfg.payments.quote_ttl_seconds
    assert request.reference.startswith("hfq1.")
    assert request.metadata["provider_agent_wallet"] == PAYOUT
    assert request.metadata["fet_network"] == "stable-testnet"
    assert request.metadata["mainnet"] == "false"


async def test_a_paid_order_runs_once_the_payment_is_on_the_ledger(shop):
    request = await order(shop)
    tx_hash = shop.pay(request)  # no memo, as ASI:One's wallet pays
    (complete, answer) = await shop.commit(request, tx_hash)
    assert complete == (BUYER, CompletePayment(transaction_id=tx_hash))
    assert answer[0] == BUYER
    assert text_of(answer[1]) == "tides\n\n— Check the sources yourself."
    assert ends_session(answer[1])
    assert shop.desk.seller.store.credit(request.reference).status == "done"
    assert len(shop.chat.orders) == 0
    # The same payment again cannot buy anything.
    again = await shop.commit(request, tx_hash)
    assert isinstance(again[0][1], CancelPayment)


async def test_a_commit_without_the_reference_finds_the_order_by_its_amount(shop):
    ctx = Context()
    first = await order(shop, "research: one", ctx=ctx)
    second = await order(shop, "research: two", ctx=ctx)
    tx_hash = shop.pay(first)  # pays the older order; the code in the amount says so
    (complete, answer) = await shop.commit(first, tx_hash, ctx=ctx, reference=False)
    assert complete[1] == CompletePayment(transaction_id=tx_hash)
    assert text_of(answer[1]).startswith("one")
    assert [o.reference for o in shop.chat.orders.of(BUYER)] == [second.reference]


async def test_someone_elses_payment_cannot_pay_for_your_order(shop):
    victim = await order(shop, "research: mine")
    thief = await order(shop, "research: free ride", sender=THIEF)
    victim_tx = shop.pay(victim)
    # The order codes differ, so the victim's payment never matches the thief's order.
    stolen = await shop.commit(thief, victim_tx, sender=THIEF)
    assert isinstance(stolen[0][1], CancelPayment)
    assert "exactly" in stolen[0][1].reason
    # Nor can the thief use the victim's reference: the quote names the victim.
    stolen = await shop.commit(
        RequestPayment(
            accepted_funds=victim.accepted_funds,
            recipient=PAYOUT,
            deadline_seconds=600,
            reference=thief.reference,
        ),
        victim_tx,
        sender=THIEF,
        reference=True,
    )
    assert isinstance(stolen[0][1], CancelPayment)
    # The victim's own commit still works.
    (complete, answer) = await shop.commit(victim, victim_tx)
    assert complete[1] == CompletePayment(transaction_id=victim_tx)
    assert text_of(answer[1]).startswith("mine")


async def test_a_wrong_amount_is_refused_and_the_order_dropped(shop):
    request = await order(shop)
    short = shop.pay(request, amount=parse_fet(request.accepted_funds[0].amount) - ORDER_CODE_UNIT)
    (cancel, message) = await shop.commit(request, short)
    assert isinstance(cancel[1], CancelPayment) and cancel[1].transaction_id == short
    assert "Your payment was not accepted" in text_of(message[1])
    assert len(shop.chat.orders) == 0


async def test_a_payment_not_on_the_ledger_yet_is_checked_again(shop, monkeypatch):
    request = await order(shop)
    missing = "C" * 64
    ((_, waiting),) = await shop.commit(request, missing)
    assert "Send `check` in a minute" in text_of(waiting)
    assert shop.sleeps == list(PENDING_RETRY_DELAYS)  # waited about 50 seconds
    # Those checks used this buyer's budget of ledger checks for the minute.
    ((_, limited),) = await shop.say("check")
    assert "Send `check` in a minute" in text_of(limited)
    # A minute later the payment shows up, and "check" settles it.
    later = time.monotonic() + 61
    monkeypatch.setattr("hermes_fetch_ai.policy._clock", lambda: later)
    paid = await shop.ledger.get_tx(shop.pay(request))
    shop.ledger.add(dataclasses.replace(paid, hash=missing))
    replies = await shop.say("check")
    (complete, answer) = replies
    assert complete[1] == CompletePayment(transaction_id=missing)
    assert text_of(answer[1]).startswith("tides")


async def test_declining_the_payment_drops_the_order(shop):
    ctx = Context()
    await order(shop, ctx=ctx)
    await shop.chat.on_reject(ctx, BUYER, RejectPayment(reason="no thanks"))
    ((_, reply),) = ctx.take()
    assert "nothing was charged" in text_of(reply)
    assert len(shop.chat.orders) == 0


async def test_a_payment_for_an_order_lost_in_a_restart_is_kept(shop):
    request = await order(shop)
    tx_hash = shop.pay(request)
    shop.restart()  # the order book is gone; the payment records are not
    (complete, message) = await shop.commit(request, tx_hash)
    assert complete[1] == CompletePayment(transaction_id=tx_hash)
    assert "Send it again, starting with `research:`" in text_of(message[1])
    # Resending the request runs it without another payment.
    ((_, answer),) = await shop.say("research: tides again")
    assert text_of(answer).startswith("tides again") and ends_session(answer)
    assert shop.desk.seller.store.credit(request.reference).status == "done"


async def test_a_commit_for_no_order_is_cancelled(shop):
    request = await order(shop)
    shop.restart()
    unknown = RequestPayment(
        accepted_funds=request.accepted_funds, recipient=PAYOUT, deadline_seconds=600
    )
    (cancel, _) = await shop.commit(unknown, "D" * 64, reference=False)
    assert cancel[1] == CancelPayment(
        transaction_id="D" * 64, reason="no order is waiting for this payment"
    )
    forged = await shop.commit(
        RequestPayment(
            accepted_funds=request.accepted_funds,
            recipient=PAYOUT,
            deadline_seconds=600,
            reference="hfq1.not-ours",
        ),
        "D" * 64,
    )
    assert forged[0][1].reason == "no order matches this payment"


class Held:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def run(self, request):
        self.started.set()
        await self.release.wait()
        return ServiceResult(request, ok=True)


async def test_a_busy_service_asks_for_no_payment(tmp_path):
    held = Held()
    cfg = config(
        research={
            "title": "Research a topic",
            "description": "Finds sources.",
            "price": "0.05",
            "runner": {"type": "echo"},
            "max_running": 1,
            "max_waiting": 0,
        }
    )
    shop = Shop(tmp_path, cfg, runners={"research": held})
    try:
        request = await order(shop)
        tx_hash = shop.pay(request)
        running = asyncio.create_task(shop.commit(request, tx_hash))
        await held.started.wait()
        ((_, reply),) = await shop.say("research: another")
        assert text_of(reply) == "This service is busy; try again in a few minutes."
        held.release.set()
        await running
    finally:
        shop.close()


async def test_a_failed_run_keeps_the_payment_for_a_resend(tmp_path):
    class Flaky:
        def __init__(self):
            self.calls = 0

        async def run(self, request):
            self.calls += 1
            if self.calls == 1:
                return ServiceResult("", ok=False, problem="the model server is down")
            return ServiceResult(request, ok=True)

    shop = Shop(tmp_path, runners={"research": Flaky()})
    try:
        request = await order(shop)
        (_, failed) = await shop.commit(request, shop.pay(request))
        assert text_of(failed[1]) == (
            "The model server is down; your payment is kept, so send the same request "
            "again to retry."
        )
        assert not ends_session(failed[1])
        ((_, answer),) = await shop.say("research: tides")
        assert text_of(answer).startswith("tides")
    finally:
        shop.close()


async def test_owner_controls_and_limits_apply_to_chat(shop):
    shop.desk.seller.store.set_paused(True)
    ((_, reply),) = await shop.say("research: x")
    assert text_of(reply) == "This agent is not taking requests right now."
    shop.desk.seller.store.set_paused(False)
    shop.desk.seller.store.ban(BUYER, reason="spam", now_ms=1)
    ((_, reply),) = await shop.say("research: x")
    assert text_of(reply) == "This agent does not accept your requests."
    shop.desk.seller.store.unban(BUYER)
    ((_, reply),) = await shop.say("research: " + "x" * 5000)
    assert text_of(reply) == (
        "Your request is 5000 characters long; **Research a topic** takes at most 4000."
    )


async def test_chat_is_rate_limited(tmp_path):
    cfg = config()
    cfg.policy.max_calls_per_minute_per_sender = 1
    shop = Shop(tmp_path, cfg)
    try:
        await shop.say("hello")
        ((_, reply),) = await shop.say("hello")
        assert text_of(reply) == "Rate limit exceeded; please wait a minute."
    finally:
        shop.close()


def test_order_book_is_bounded_and_prefers_the_current_session():
    book = OrderBook(limit=2)
    book.add(Order("r1", BUYER, "s1", "research", "a"))
    book.add(Order("r2", BUYER, "s2", "research", "b"))
    book.add(Order("r3", THIEF, "s3", "research", "c"))
    assert book.get("r1") is None and len(book) == 2  # the oldest went first
    assert [o.reference for o in book.of(BUYER, "s2")] == ["r2"]
    book.add(Order("r4", BUYER, "s1", "research", "d"))
    assert [o.reference for o in book.of(BUYER, "s2")] == ["r4"]
    assert book.get(None) is None


def test_chat_quotes_bind_the_service_not_the_request_text():
    assert chat_digest("research") == chat_digest("research")
    assert chat_digest("research") != chat_digest("free")


@pytest.mark.parametrize(
    ("text", "expected"),
    [("busy now", "Busy now."), ("done!", "Done!"), ("", ""), ("ok.", "Ok.")],
)
def test_sentence(text, expected):
    assert sentence(text) == expected


async def test_funds_amount_is_a_string_asi_one_can_show():
    funds = Funds(amount="0.050000000001234", currency="FET", payment_method="fet_direct")
    assert isinstance(funds.amount, str)


async def test_a_payment_that_arrives_while_paused_is_kept_for_later(shop):
    request = await order(shop)
    shop.desk.seller.store.set_paused(True)
    (complete, message) = await shop.commit(request, shop.pay(request))
    assert isinstance(complete[1], CompletePayment)
    assert "paused its work. The payment is kept" in text_of(message[1])
    assert shop.desk.seller.store.credit(request.reference).status == "paid"
    shop.desk.seller.store.set_paused(False)
    ((_, answer),) = await shop.say("research: tides")
    assert text_of(answer).startswith("tides")


async def test_a_banned_agent_cannot_commit(shop):
    request = await order(shop)
    shop.desk.seller.store.ban(BUYER, reason="abuse", now_ms=1)
    ((_, cancel),) = await shop.commit(request, shop.pay(request))
    assert cancel == CancelPayment(
        transaction_id=cancel.transaction_id, reason="this agent does not accept your requests"
    )
    assert shop.desk.seller.store.credit(request.reference) is None
