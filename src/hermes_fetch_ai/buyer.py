"""Buying from other agents, with the owner's approval for every payment.

Hermes reaches other agents through the bridge. The bridge sends Hermes'
messages over Fetch's chat protocol, keeps the replies for Hermes to read,
and records each payment request it gets (the Agent Payment Protocol, buyer
role). It pays a request only when the owner approved that exact request,
and only within the limits in ``buying``:

- testnet FET only, from the buying wallet (key index 1), never the income
  wallet;
- payment requests count only from an agent Hermes is talking to, in testnet
  FET paid directly (``fet_direct``) to a ``fetch1`` wallet;
- an approval names the amount, the recipient, and a one-time code issued
  when the request was shown, so a payment is always for what the owner saw;
- the per-payment, per-seller, and daily limits are checked in the same
  database transaction that marks a payment as being sent;
- a payment's transaction hash is recorded before it is broadcast. A payment
  whose outcome is unknown waits for the owner (``check``), who can look it up
  on the ledger; it is never sent again on its own.

Everything other agents say is kept as untrusted text for Hermes to read;
none of it is ever followed as an instruction by the bridge.
"""

from __future__ import annotations

import asyncio
import contextlib
import secrets
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from uagents import Context
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
from uagents_core.models import Model

from .audit import AuditWriter
from .config import BridgeConfig, is_agent_address, is_fetch_address
from .ledger import LedgerReader, LedgerUnavailable
from .logging import get_logger
from .money import MAX_PRICE_BASE, format_fet, parse_fet
from .seller import short_tx
from .sender import PaymentSender
from .store import InboxEntry, Purchase, PurchaseRefused, Store

logger = get_logger("hermes_fetch_ai")

# Metadata the seller's side reads (Fetch's FET payment example).
FET_NETWORK = "stable-testnet"
PURCHASE_ID_PREFIX = "pay-"
MAX_DESCRIPTION_CHARS = 500
MAX_REPLY_CHARS = 20_000
# Payment requests from one agent waiting for the owner; older ones expire.
MAX_OPEN_QUOTES_PER_SELLER = 20
# Longest a payment request may stay open, whatever the seller asks.
MAX_DEADLINE_SECONDS = 3600
# A payment that never showed up on the ledger after this long is given up on.
GIVE_UP_AFTER_MS = 3_600_000
# Quiet seconds after which a burst of replies counts as complete.
SETTLE_SECONDS = 1.5
# Most replies, and most characters of them, handed back at once; the rest
# wait in the inbox for the next read.
MAX_REPLIES_AT_ONCE = 50
MAX_REPLIES_CHARS = 60_000

SendInSession = Callable[[str, Model, str], Awaitable[None]]


def new_purchase_id() -> str:
    return PURCHASE_ID_PREFIX + secrets.token_hex(4)


def _clean(text: str, limit: int) -> str:
    """Untrusted text, without control characters (except newlines and tabs), capped."""
    cleaned = "".join(ch for ch in text if ch in "\n\t" or (ch.isprintable() and ch != "\x7f"))
    return cleaned if len(cleaned) <= limit else cleaned[:limit] + "…"


@dataclass(frozen=True)
class QuoteTerms:
    amount_base: int
    recipient: str
    reference: str | None
    description: str
    deadline_ms: int


def check_request(msg: RequestPayment, *, now_ms: int) -> QuoteTerms:
    """The terms of a seller's payment request, or ValueError with what is wrong."""
    funds = next(
        (
            f
            for f in msg.accepted_funds
            if f.currency.upper() == "FET" and f.payment_method == "fet_direct"
        ),
        None,
    )
    if funds is None:
        raise ValueError("only testnet FET paid directly (fet_direct) is accepted")
    try:
        amount = parse_fet(funds.amount)
    except ValueError:
        raise ValueError("the amount is not a FET amount") from None
    if not 0 < amount <= MAX_PRICE_BASE:
        raise ValueError(f"the amount must be more than 0 and at most {format_fet(MAX_PRICE_BASE)}")
    if not is_fetch_address(msg.recipient):
        raise ValueError("the recipient is not a fetch1... wallet address")
    metadata = msg.metadata or {}
    network = metadata.get("fet_network")
    if network is not None and network not in (FET_NETWORK, "testnet", "dorado-1"):
        raise ValueError("only Fetch's testnet is accepted")
    if str(metadata.get("mainnet", "false")).lower() == "true":
        raise ValueError("only Fetch's testnet is accepted")
    if msg.deadline_seconds <= 0:
        raise ValueError("the payment request has already expired")
    reference = msg.reference
    if reference is not None and (len(reference) > 256 or not reference.isprintable()):
        raise ValueError("the reference is not usable as a payment memo")
    deadline = min(msg.deadline_seconds, MAX_DEADLINE_SECONDS)
    return QuoteTerms(
        amount_base=amount,
        recipient=msg.recipient,
        reference=reference,
        description=_clean(msg.description or "", MAX_DESCRIPTION_CHARS),
        deadline_ms=now_ms + deadline * 1000,
    )


def text_of(msg: ChatMessage) -> str:
    return "\n".join(item.text for item in msg.content if isinstance(item, TextContent))


def first_replies(entries: list[InboxEntry]) -> list[InboxEntry]:
    """The oldest of ``entries`` that fit in one answer (always at least one)."""
    kept: list[InboxEntry] = []
    chars = 0
    for entry in entries[:MAX_REPLIES_AT_ONCE]:
        chars += len(entry.body)
        if kept and chars > MAX_REPLIES_CHARS:
            break
        kept.append(entry)
    return kept


class Buyer:
    """The buying side of the bridge: talking to other agents and paying them."""

    def __init__(
        self,
        cfg: BridgeConfig,
        store: Store,
        audit: AuditWriter,
        *,
        sender: PaymentSender | None,
        ledger_factory: Callable[[], LedgerReader],
        clock: Callable[[], float] = time.time,
        new_id: Callable[[], str] = new_purchase_id,
    ) -> None:
        self.cfg = cfg
        self.store = store
        self.audit = audit
        self.sender = sender
        self._ledger_factory = ledger_factory
        self._ledger: LedgerReader | None = None
        self._clock = clock
        self._new_id = new_id
        # Set by the agent once it runs: sends a message in a given chat session.
        self.send: SendInSession | None = None
        # One event per waiting caller, set when its conversation gets a message.
        self._arrivals: dict[tuple[str, str], set[asyncio.Event]] = {}

    def _now_ms(self) -> int:
        return int(self._clock() * 1000)

    def _audit(self, peer: str, msg_type: str, decision: str, reason: str, **extra: Any) -> None:
        self.audit.write(
            trace_id=str(uuid.uuid4()),
            sender=peer,
            protocol="buy",
            msg_type=msg_type,
            decision=decision,
            reason=reason,
            **extra,
        )

    def _arrived(self, peer: str, session: str) -> None:
        for event in self._arrivals.get((peer, session), ()):
            event.set()

    # -- talking ------------------------------------------------------------

    async def message(self, to: str, text: str, session: str | None = None) -> tuple[str, int]:
        """Send Hermes' text to an agent; returns the session and the last inbox id before it."""
        if self.send is None:
            raise PurchaseRefused("the bridge is not running")
        if not is_agent_address(to):
            raise PurchaseRefused("that is not an agent address (agent1...)")
        if not text.strip():
            raise PurchaseRefused("the message is empty")
        if len(text) > self.cfg.buying.max_message_chars:
            raise PurchaseRefused(
                f"the message is longer than {self.cfg.buying.max_message_chars} characters"
            )
        if session is None:
            session = str(uuid.uuid4())
        else:
            try:
                session = str(uuid.UUID(session))
            except ValueError:
                raise PurchaseRefused("that is not a conversation id") from None
            if not self.store.has_conversation(to, session):
                raise PurchaseRefused("there is no such conversation with this agent")
        mark = self.store.last_message_id()
        self.store.open_conversation(to, session, now_ms=self._now_ms())
        await self.send(to, ChatMessage(content=[TextContent(text=text)]), session)
        self._audit(to, "message", "allowed", "sent", output_bytes=len(text.encode("utf-8")))
        return session, mark

    async def wait_for_reply(
        self,
        peer: str,
        session: str,
        *,
        after_id: int,
        timeout: float,
        settle: float = SETTLE_SECONDS,
        answers: Callable[[InboxEntry], bool] = lambda entry: True,
    ) -> list[InboxEntry]:
        """New messages in a conversation, waiting up to ``timeout`` seconds for an answer.

        An answer is a message ``answers`` accepts (by default, any message).
        Agents often answer with several messages at once (a price, then a
        payment request), so once an answer arrives this keeps collecting until
        the conversation has been quiet for ``settle`` seconds, or until there
        is more than one reply can hold (``first_replies``); the rest wait in
        the inbox.
        """
        key = (peer, session)
        event = asyncio.Event()
        waiting = self._arrivals.setdefault(key, set())
        waiting.add(event)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        try:
            entries = self.store.inbox(peer=peer, session=session, after_id=after_id)
            while len(first_replies(entries)) == len(entries):
                answered = any(answers(entry) for entry in entries)
                left = deadline - loop.time()
                wait = min(settle, left) if answered else left
                if wait <= 0:
                    break
                event.clear()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(event.wait(), wait)
                more = self.store.inbox(
                    peer=peer, session=session, after_id=entries[-1].id if entries else after_id
                )
                if answered and not more:
                    break  # quiet for `settle` seconds
                entries += more
            return first_replies(entries)
        finally:
            waiting.discard(event)
            if not waiting:
                self._arrivals.pop(key, None)

    def expects(self, peer: str, session: str | None = None) -> bool:
        """True for an agent Hermes started talking to (in this session, if given)."""
        return self.store.has_conversation(peer, session)

    async def on_chat(self, ctx: Context, peer: str, msg: ChatMessage) -> None:
        await ctx.send(peer, ChatAcknowledgement(acknowledged_msg_id=msg.msg_id))
        session = str(ctx.session)
        text = text_of(msg)
        if text:
            self.store.add_message(
                peer=peer,
                session=session,
                kind="text",
                body=_clean(text, MAX_REPLY_CHARS),
                now_ms=self._now_ms(),
            )
        if any(isinstance(item, EndSessionContent) for item in msg.content):
            self.store.add_message(
                peer=peer, session=session, kind="end", body="", now_ms=self._now_ms()
            )
        self._audit(peer, "reply", "allowed", "kept", output_bytes=len(text.encode("utf-8")))
        self._arrived(peer, session)

    # -- payment requests ---------------------------------------------------

    async def on_request_payment(self, ctx: Context, peer: str, msg: RequestPayment) -> None:
        session = str(ctx.session)
        if not self.expects(peer):
            # Only agents Hermes is talking to may ask it for money.
            self._audit(peer, "payment_request", "denied", "no conversation")
            await ctx.send(peer, RejectPayment(reason="this agent did not ask you for anything"))
            return
        now = self._now_ms()
        try:
            terms = check_request(msg, now_ms=now)
        except ValueError as exc:
            self._audit(peer, "payment_request", "denied", str(exc))
            self.store.add_message(
                peer=peer,
                session=session,
                kind="payment_refused",
                body=f"The agent asked for a payment that cannot be made: {exc}.",
                now_ms=now,
            )
            await ctx.send(peer, RejectPayment(reason=str(exc)))
            self._arrived(peer, session)
            return
        open_quotes = self.store.open_quotes(peer, session)
        for stale in open_quotes[MAX_OPEN_QUOTES_PER_SELLER - 1 :]:
            self.store.move_purchase(stale.id, from_states=("quoted",), to="expired", now_ms=now)
        purchase = self.store.add_quote(
            purchase_id=self._new_id(),
            peer=peer,
            session=session,
            reference=terms.reference,
            recipient=terms.recipient,
            amount_base=terms.amount_base,
            description=terms.description,
            deadline_ms=terms.deadline_ms,
            now_ms=now,
        )
        self.store.add_message(
            peer=peer,
            session=session,
            kind="payment_request",
            body=(
                f"The agent asks for {format_fet(terms.amount_base)} testnet FET "
                f"(payment request {purchase.id}): {terms.description or 'no description'}"
            ),
            now_ms=now,
        )
        self._audit(
            peer,
            "payment_request",
            "allowed",
            "waiting for the owner",
            purchase=purchase.id,
            amount_base=str(terms.amount_base),
        )
        self._arrived(peer, session)

    def show(self, purchase_id: str) -> Purchase:
        """A payment request as the owner will see it, with a fresh one-time code."""
        return self.store.issue_nonce(purchase_id, secrets.token_hex(8), now_ms=self._now_ms())

    async def decline(self, purchase_id: str, reason: str = "the owner declined") -> Purchase:
        purchase = self.store.move_purchase(
            purchase_id, from_states=("quoted",), to="declined", now_ms=self._now_ms(), note=reason
        )
        if self.send is not None:
            await self.send(purchase.peer, RejectPayment(reason=reason), purchase.session)
        self._audit(purchase.peer, "pay", "denied", reason, purchase=purchase.id)
        return purchase

    async def pay(
        self, purchase_id: str, *, nonce: str, expect_amount_base: int, expect_recipient: str
    ) -> Purchase:
        """Pay an approved request: check it and the limits, send, and tell the seller."""
        if self.sender is None or self.send is None:
            raise PurchaseRefused("buying is not running; start the bridge with buying enabled")
        buying = self.cfg.buying
        purchase = self.store.start_payment(
            purchase_id,
            nonce=nonce,
            expect_amount_base=expect_amount_base,
            expect_recipient=expect_recipient,
            max_payment_base=buying.max_payment_base,
            max_per_day_base=buying.max_per_day_base,
            max_per_seller_base=buying.max_per_seller_per_day_base,
            allowed_sellers=buying.allowed_sellers,
            now_ms=self._now_ms(),
        )

        def record(tx_hash: str) -> None:
            self.store.set_purchase_tx(purchase.id, tx_hash, now_ms=self._now_ms())

        try:
            outcome = await self.sender.send(
                recipient=purchase.recipient,
                amount_base=purchase.amount_base,
                memo=purchase.reference or "",
                before_broadcast=record,
            )
        except Exception:  # the payment may have left; never assume it did not
            logger.exception("payment %s: sending failed unexpectedly", purchase.id)
            return self._needs_review(purchase.id, "sending failed unexpectedly; run check")
        if outcome.status == "rejected":
            self._audit(
                purchase.peer, "pay", "error", outcome.problem or "rejected", purchase=purchase.id
            )
            return self.store.move_purchase(
                purchase.id,
                from_states=("broadcasting",),
                to="failed",
                now_ms=self._now_ms(),
                note=outcome.problem or "the ledger rejected the payment; nothing was sent",
            )
        if outcome.status == "unknown":
            return self._needs_review(purchase.id, outcome.problem or "the outcome is unknown")
        if outcome.tx_hash and outcome.tx_hash != self._stored_tx(purchase.id):
            self.store.set_purchase_tx(purchase.id, outcome.tx_hash, now_ms=self._now_ms())
        paid = self.store.move_purchase(
            purchase.id, from_states=("broadcasting",), to="paid", now_ms=self._now_ms()
        )
        self._audit(
            paid.peer,
            "pay",
            "allowed",
            "paid",
            purchase=paid.id,
            amount_base=str(paid.amount_base),
            tx_short=short_tx(paid.tx_hash or ""),
        )
        return await self._commit(paid)

    def _stored_tx(self, purchase_id: str) -> str | None:
        stored = self.store.purchase(purchase_id)
        return stored.tx_hash if stored else None

    def _needs_review(self, purchase_id: str, note: str) -> Purchase:
        purchase = self.store.move_purchase(
            purchase_id,
            from_states=("broadcasting",),
            to="needs_review",
            now_ms=self._now_ms(),
            note=note,
        )
        self._audit(purchase.peer, "pay", "error", "outcome unknown", purchase=purchase.id)
        return purchase

    async def _commit(self, purchase: Purchase) -> Purchase:
        """Tell the seller the payment is made; a failure here leaves it paid, to retry."""
        assert self.send is not None and self.sender is not None and purchase.tx_hash
        commit = CommitPayment(
            funds=Funds(
                amount=format_fet(purchase.amount_base), currency="FET", payment_method="fet_direct"
            ),
            recipient=purchase.recipient,
            transaction_id=purchase.tx_hash,
            reference=purchase.reference,
            description=purchase.description[:200] or None,
            metadata={"buyer_fet_wallet": self.sender.address(), "fet_network": FET_NETWORK},
        )
        # Recorded first: the seller's confirmation can arrive before send() returns.
        self.store.move_purchase(
            purchase.id, from_states=("paid",), to="committed", now_ms=self._now_ms()
        )
        try:
            await self.send(purchase.peer, commit, purchase.session)
        except Exception:  # the payment is made; telling the seller can be retried
            logger.exception("payment %s: could not tell the seller", purchase.id)
            return self.store.move_purchase(
                purchase.id, from_states=("committed",), to="paid", now_ms=self._now_ms()
            )
        latest = self.store.purchase(purchase.id)
        assert latest is not None
        return latest

    async def check(self, purchase_id: str) -> Purchase:
        """Settle a payment whose outcome was unknown, or retry telling the seller."""
        purchase = self.store.purchase(purchase_id)
        if purchase is None:
            raise PurchaseRefused(f"no payment {purchase_id}")
        if purchase.status == "paid":
            return await self._commit(purchase)
        if purchase.status != "needs_review":
            return purchase
        if not purchase.tx_hash:
            # It failed before a transaction existed, so nothing was sent.
            return self.store.move_purchase(
                purchase.id,
                from_states=("needs_review",),
                to="failed",
                now_ms=self._now_ms(),
                note="no transaction was made",
            )
        if self._ledger is None:
            self._ledger = self._ledger_factory()
        try:
            tx = await self._ledger.get_tx(purchase.tx_hash)
        except LedgerUnavailable as exc:
            raise PurchaseRefused(f"the ledger cannot be reached: {exc}") from None
        now = self._now_ms()
        if tx is None:
            if purchase.spent_ms is not None and now - purchase.spent_ms > GIVE_UP_AFTER_MS:
                return self.store.move_purchase(
                    purchase.id,
                    from_states=("needs_review",),
                    to="failed",
                    now_ms=now,
                    note="the payment never appeared on the ledger",
                )
            return purchase
        sent = sum(
            transfer.amount
            for transfer in tx.transfers
            if transfer.recipient == purchase.recipient
            and transfer.denom == self.cfg.payments.denom
        )
        if tx.code != 0 or sent < purchase.amount_base:
            return self.store.move_purchase(
                purchase.id,
                from_states=("needs_review",),
                to="failed",
                now_ms=now,
                note="the payment failed on the ledger",
            )
        paid = self.store.move_purchase(
            purchase.id, from_states=("needs_review",), to="paid", now_ms=now
        )
        return await self._commit(paid)

    # -- the seller's answers -----------------------------------------------

    def _purchase_for(self, peer: str, session: str, transaction_id: str | None) -> Purchase | None:
        if transaction_id:
            found = self.store.purchase_by_tx(transaction_id.upper().removeprefix("0X"))
            return found if found is not None and found.peer == peer else None
        for purchase in self.store.purchases(status="committed", limit=200):
            if purchase.peer == peer and purchase.session == session:
                return purchase
        return None

    async def on_complete(self, ctx: Context, peer: str, msg: CompletePayment) -> None:
        purchase = self._purchase_for(peer, str(ctx.session), msg.transaction_id)
        if purchase is None:
            self._audit(peer, "complete", "denied", "unknown payment")
            return
        try:
            done = self.store.move_purchase(
                purchase.id,
                from_states=("paid", "committed"),
                to="completed",
                now_ms=self._now_ms(),
            )
        except PurchaseRefused:
            return
        self.store.add_message(
            peer=peer,
            session=done.session,
            kind="payment_complete",
            body=f"The agent confirmed payment {done.id}.",
            now_ms=self._now_ms(),
        )
        self._audit(peer, "complete", "allowed", "seller confirmed", purchase=done.id)
        self._arrived(peer, done.session)

    async def on_cancel(self, ctx: Context, peer: str, msg: CancelPayment) -> None:
        purchase = self._purchase_for(peer, str(ctx.session), msg.transaction_id)
        if purchase is None:
            self._audit(peer, "cancel", "denied", "unknown payment")
            return
        reason = _clean(msg.reason or "no reason given", MAX_DESCRIPTION_CHARS)
        try:
            cancelled = self.store.move_purchase(
                purchase.id,
                from_states=("paid", "committed"),
                to="cancelled",
                now_ms=self._now_ms(),
                note=reason,
            )
        except PurchaseRefused:
            return
        self.store.add_message(
            peer=peer,
            session=cancelled.session,
            kind="payment_cancelled",
            body=(
                f"The agent cancelled payment {cancelled.id} after it was made: {reason}. "
                "Ask it for a refund."
            ),
            now_ms=self._now_ms(),
        )
        self._audit(peer, "cancel", "error", "seller cancelled", purchase=cancelled.id)
        self._arrived(peer, cancelled.session)

    async def aclose(self) -> None:
        if self._ledger is not None:
            await self._ledger.aclose()
            self._ledger = None
