"""Selling services in plain language: Fetch's chat protocol with the payment protocol.

ASI:One users, and any agent that speaks AgentChatProtocol 0.3.0, write to the
bridge in plain text. The bridge answers with its menu of services and
prices, asks for payment with the Agent Payment Protocol (seller role) in the
shape ASI:One's payment card expects, reads the payment from the ledger
itself, runs the service, and replies with the answer. Chat reaches only the
services the owner sells, never the owner's Hermes tools.

A chat payment may arrive without our reference in its memo (ASI:One's wallet
is not known to set one), so a chat price carries an order code: a small
random surcharge that ties the payment's exact amount to one order.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from uagents import Context, Protocol
from uagents_core.contrib.protocols.chat import (
    AgentContent,
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)
from uagents_core.contrib.protocols.payment import (
    CancelPayment,
    CommitPayment,
    CompletePayment,
    Funds,
    RejectPayment,
    RequestPayment,
    payment_protocol_spec,
)

from .audit import AuditWriter
from .buyer import Buyer
from .chat_menu import ask_for_request, menu, pick_service, price_text
from .config import BridgeConfig
from .money import format_fet
from .policy import PolicyState, consume_call_rate
from .quotes import request_digest
from .seller import PaymentProof, PaymentRefused, short_reference
from .services import BUSY, ServiceDesk, credit_audit, service_tool_name
from .store import Credit

# ASI:One's payment card reads these metadata keys (Fetch's fet-example seller).
FET_NETWORK = "stable-testnet"
# Waits between ledger checks while a committed payment is not visible yet.
# Six checks in about 50 seconds stay within the default 6 per minute per buyer.
PENDING_RETRY_DELAYS = (3.0, 5.0, 8.0, 13.0, 21.0)
MAX_ORDERS = 256
# Orders a payment without a reference may belong to, newest first.
_MAX_ORDERS_TRIED = 3
CHECK_WORDS = frozenset({"check", "check payment", "status"})
RETRY_HINT = "; your payment is kept, so send the same request again to retry"
_PENDING_STATUSES = frozenset({"pending", "limited"})


def chat_digest(service: str) -> str:
    """What a chat quote binds besides the buyer: the service, not the request text.

    The request itself waits in the order book. Binding the quote to the
    service lets a payment be verified even after a restart lost the order.
    """
    return request_digest({"chat": service})


def sentence(text: str) -> str:
    """A refusal reason as a sentence: capitalized, with a full stop."""
    text = text.strip()
    if not text:
        return text
    text = text[0].upper() + text[1:]
    return text if text.endswith((".", "!", "?")) else text + "."


@dataclass
class Order:
    reference: str
    sender: str
    session: str
    service: str
    request: str
    tx_hash: str | None = None


class OrderBook:
    """Orders waiting for payment, oldest first; in memory and bounded."""

    def __init__(self, limit: int = MAX_ORDERS) -> None:
        self._orders: OrderedDict[str, Order] = OrderedDict()
        self._limit = limit

    def add(self, order: Order) -> None:
        self._orders[order.reference] = order
        while len(self._orders) > self._limit:
            self._orders.popitem(last=False)

    def get(self, reference: str | None) -> Order | None:
        return self._orders.get(reference) if reference else None

    def of(self, sender: str, session: str | None = None) -> list[Order]:
        """The sender's orders, newest first; those in ``session`` before the rest."""
        mine = [order for order in reversed(self._orders.values()) if order.sender == sender]
        return sorted(mine, key=lambda order: order.session != session)

    def remove(self, reference: str) -> None:
        self._orders.pop(reference, None)

    def __len__(self) -> int:
        return len(self._orders)


class ChatDesk:
    """Answers chat and payment messages for the services a bridge sells."""

    def __init__(
        self,
        cfg: BridgeConfig,
        desk: ServiceDesk,
        audit: AuditWriter,
        state: PolicyState | None = None,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.cfg = cfg
        self.desk = desk
        self.audit = audit
        self.state = state or PolicyState()
        self.orders = OrderBook()
        self._sleep = sleep

    # -- small helpers ----------------------------------------------------

    async def _say(self, ctx: Context, to: str, text: str, *, end: bool = False) -> None:
        content: list[AgentContent] = [TextContent(text=text)]
        if end:
            content.append(EndSessionContent())
        await ctx.send(to, ChatMessage(content=content))

    def _audit(
        self,
        sender: str,
        msg_type: str,
        decision: str,
        reason: str,
        service: str | None = None,
        **extra: Any,
    ) -> None:
        self.audit.write(
            trace_id=str(uuid.uuid4()),
            sender=sender,
            protocol="chat",
            msg_type=msg_type,
            tool=service_tool_name(service) if service else None,
            decision=decision,
            reason=reason,
            **extra,
        )

    # -- chat ---------------------------------------------------------------

    async def on_chat(self, ctx: Context, sender: str, msg: ChatMessage) -> None:
        # Acknowledge first, as the chat protocol expects, before any slow work.
        await ctx.send(sender, ChatAcknowledgement(acknowledged_msg_id=msg.msg_id))
        ok, why = consume_call_rate(sender, self.cfg.policy, self.state)
        if not ok:
            self._audit(sender, "chat", "denied", why)
            await self._say(ctx, sender, sentence(f"{why}; please wait a minute"))
            return
        store = self.desk.seller.store
        if store.paused():
            await self._say(ctx, sender, "This agent is not taking requests right now.")
            return
        if store.is_banned(sender):
            await self._say(ctx, sender, "This agent does not accept your requests.")
            return
        text = msg.text().strip()
        session = str(ctx.session)
        if text.lower() in CHECK_WORDS:
            waiting = [order for order in self.orders.of(sender, session) if order.tx_hash]
            if waiting:
                await self._settle(ctx, sender, waiting[0], str(waiting[0].tx_hash))
                return
        services = self.desk.cfg.services
        picked = pick_service(text, services)
        if picked is None:
            self._audit(sender, "chat", "menu", "menu")
            await self._say(ctx, sender, menu(self.cfg.agent.name, services))
            return
        name, request = picked
        svc = services[name]
        if not request:
            await self._say(ctx, sender, ask_for_request(name, svc))
            return
        if len(request) > svc.input.max_chars:
            await self._say(
                ctx,
                sender,
                f"Your request is {len(request)} characters long; **{svc.title}** takes at "
                f"most {svc.input.max_chars}.",
            )
            return
        problem = await self.desk.admit(name, sender, {"request": request})
        if problem is not None:
            self._audit(sender, "chat", "denied", problem, name)
            await self._say(ctx, sender, sentence(problem))
            return
        if not svc.price_base:
            await self._deliver(ctx, sender, name, request, None)
            return
        credit = store.unused_credit(sender=sender, subject=name, digest=chat_digest(name))
        if credit is not None:
            # Paid earlier for an order the bridge lost (or a failed run): use that payment.
            await self._deliver(ctx, sender, name, request, credit)
            return
        if self.desk.busy(name):
            # Never ask for money that cannot be worked off soon.
            await self._say(ctx, sender, sentence(BUSY))
            return
        await self._ask_for_payment(ctx, sender, session, name, request)

    async def _ask_for_payment(
        self, ctx: Context, sender: str, session: str, name: str, request: str
    ) -> None:
        svc = self.desk.cfg.services[name]
        seller = self.desk.seller
        quote, reference = seller.quote(
            kind="chat",
            sender=sender,
            subject=name,
            digest=chat_digest(name),
            amount_base=svc.price_base,
        )
        self.orders.add(Order(reference, sender, session, name, request))
        amount = format_fet(quote.amount_base)
        self._audit(
            sender,
            "chat",
            "payment",
            "payment required",
            name,
            payment="required",
            credit=short_reference(reference),
            amount_base=str(quote.amount_base),
        )
        await self._say(
            ctx,
            sender,
            f"**{svc.title}** costs {price_text(svc)}. Approve the payment of {amount} "
            "testnet FET to start. The last digits are this order's code, so your "
            "payment cannot be mixed up with anyone else's.",
        )
        await ctx.send(
            sender,
            RequestPayment(
                accepted_funds=[Funds(amount=amount, currency="FET", payment_method="fet_direct")],
                recipient=seller.payout,
                deadline_seconds=self.cfg.payments.quote_ttl_seconds,
                reference=reference,
                description=f"{svc.title} ({amount} testnet FET)",
                metadata={
                    "provider_agent_wallet": seller.payout,
                    "fet_network": FET_NETWORK,
                    "mainnet": "false",
                    "service": name,
                    "agent": self.cfg.agent.name,
                },
            ),
        )

    async def _deliver(
        self, ctx: Context, to: str, name: str, request: str, credit: Credit | None
    ) -> None:
        audit = credit_audit(credit) if credit is not None else {}
        outcome = await self.desk.serve(name, to, request, credit, audit, retry_hint=RETRY_HINT)
        self._audit(
            to,
            "chat",
            outcome.decision,
            outcome.reason,
            name,
            output_bytes=outcome.output_bytes,
            truncated=outcome.truncated,
            **outcome.audit,
        )
        text = outcome.text if not outcome.is_error else sentence(outcome.text)
        await self._say(ctx, to, text, end=not outcome.is_error)

    # -- payment ------------------------------------------------------------

    async def on_commit(self, ctx: Context, sender: str, msg: CommitPayment) -> None:
        ok, why = consume_call_rate(sender, self.cfg.policy, self.state)
        if not ok:
            self._audit(sender, "payment", "denied", why)
            await ctx.send(sender, CancelPayment(transaction_id=msg.transaction_id, reason=why))
            return
        if self.desk.seller.store.is_banned(sender):
            reason = "this agent does not accept your requests"
            self._audit(sender, "payment", "denied", reason)
            await ctx.send(sender, CancelPayment(transaction_id=msg.transaction_id, reason=reason))
            return
        order = self.orders.get(msg.reference)
        if order is not None:
            order.tx_hash = msg.transaction_id
            await self._settle(ctx, sender, order, msg.transaction_id)
            return
        if msg.reference:
            # A reference this bridge issued but no longer holds (it restarted).
            await self._recover(ctx, sender, msg.reference, msg.transaction_id)
            return
        # No reference: the payment belongs to one of this buyer's orders,
        # and its exact amount (order code included) says which.
        candidates = self.orders.of(sender, str(ctx.session))[:_MAX_ORDERS_TRIED]
        for order in candidates:
            try:
                credit = await self._redeem(
                    PaymentProof(order.reference, msg.transaction_id), order
                )
            except PaymentRefused as exc:
                if "the amount must be exactly" in exc.reason and order is not candidates[-1]:
                    continue
                await self._refused(ctx, sender, order, msg.transaction_id, exc)
                return
            order.tx_hash = msg.transaction_id
            await self._settled(ctx, sender, order, msg.transaction_id, credit)
            return
        reason = "no order is waiting for this payment"
        self._audit(sender, "payment", "denied", reason)
        await ctx.send(sender, CancelPayment(transaction_id=msg.transaction_id, reason=reason))
        await self._say(ctx, sender, sentence(reason))

    async def on_reject(self, ctx: Context, sender: str, msg: RejectPayment) -> None:
        for order in self.orders.of(sender, str(ctx.session))[:1]:
            if order.tx_hash is None:
                self.orders.remove(order.reference)
        self._audit(sender, "payment", "rejected", "buyer declined")
        await self._say(ctx, sender, "No problem: nothing was charged. Send a request any time.")

    async def _redeem(self, proof: PaymentProof, order: Order) -> Credit:
        """Redeem ``proof`` for ``order``, waiting a while for a payment not yet on the ledger."""
        for attempt, delay in enumerate((0.0, *PENDING_RETRY_DELAYS)):
            if delay:
                await self._sleep(delay)
            try:
                return await self.desk.seller.redeem(
                    proof,
                    sender=order.sender,
                    subject=order.service,
                    digest=chat_digest(order.service),
                    kind="chat",
                )
            except PaymentRefused as exc:
                if exc.status not in _PENDING_STATUSES or attempt == len(PENDING_RETRY_DELAYS):
                    raise
        raise AssertionError("unreachable")  # pragma: no cover

    async def _settle(self, ctx: Context, committer: str, order: Order, tx_hash: str) -> None:
        try:
            credit = await self._redeem(PaymentProof(order.reference, tx_hash), order)
        except PaymentRefused as exc:
            await self._refused(ctx, committer, order, tx_hash, exc)
            return
        await self._settled(ctx, committer, order, tx_hash, credit)

    async def _settled(
        self, ctx: Context, committer: str, order: Order, tx_hash: str, credit: Credit
    ) -> None:
        await ctx.send(committer, CompletePayment(transaction_id=tx_hash))
        self.orders.remove(order.reference)
        if self.desk.seller.store.paused():
            # The owner stopped selling after this order: keep the payment for later.
            self._audit(
                order.sender, "payment", "allowed", "payment kept while paused", order.service
            )
            await self._say(
                ctx,
                order.sender,
                "Your payment arrived, but this agent has paused its work. The payment is "
                f"kept: send your request again later, starting with `{order.service}:`, and it "
                "will run without another payment.",
            )
            return
        await self._deliver(ctx, order.sender, order.service, order.request, credit)

    async def _refused(
        self, ctx: Context, committer: str, order: Order, tx_hash: str, exc: PaymentRefused
    ) -> None:
        self._audit(committer, "payment", "denied", exc.reason, order.service, payment=exc.status)
        if exc.status in _PENDING_STATUSES:
            await self._say(
                ctx,
                order.sender,
                "I can't see your payment on the ledger yet. Send `check` in a minute "
                "and I'll look again.",
            )
            return
        await ctx.send(committer, CancelPayment(transaction_id=tx_hash, reason=exc.reason))
        # Only the buyer who ordered can lose the order; anyone else just gets the cancel.
        if committer == order.sender:
            self.orders.remove(order.reference)
            await self._say(
                ctx, order.sender, sentence(f"your payment was not accepted: {exc.reason}")
            )

    async def _recover(self, ctx: Context, sender: str, reference: str, tx_hash: str) -> None:
        """Accept a payment for an order the bridge lost; the buyer then resends the request."""
        for name, svc in self.desk.cfg.services.items():
            order = Order(reference, sender, "", name, "")
            try:
                await self._redeem(PaymentProof(reference, tx_hash), order)
            except PaymentRefused as exc:
                if exc.status == "mismatch":
                    continue  # the reference was issued for another service
                await self._refused(ctx, sender, order, tx_hash, exc)
                return
            await ctx.send(sender, CompletePayment(transaction_id=tx_hash))
            self._audit(sender, "payment", "allowed", "payment kept for a resent request", name)
            await self._say(
                ctx,
                sender,
                f"I received your payment for **{svc.title}**, but I no longer have your "
                f"request. Send it again, starting with `{name}:`, and it will run without "
                "another payment.",
            )
            return
        reason = "no order matches this payment"
        self._audit(sender, "payment", "denied", reason)
        await ctx.send(sender, CancelPayment(transaction_id=tx_hash, reason=reason))
        await self._say(ctx, sender, sentence(reason))


def build_chat_protocols(
    cfg: BridgeConfig,
    desk: ServiceDesk | None,
    audit: AuditWriter,
    buyer: Buyer | None = None,
) -> list[Protocol]:
    """Fetch's chat protocol, and the payment protocol for each side the bridge takes.

    A selling bridge answers chat with its services and takes the payment
    protocol's seller role; a buying bridge keeps the replies to the
    conversations Hermes started and takes the buyer role. Replies in a
    conversation Hermes started go to the buyer; everything else goes to
    the sales desk (or, on a bridge that does not sell through chat, is only
    acknowledged).
    """
    chat_desk = ChatDesk(cfg, desk, audit) if desk is not None and cfg.chat.enable_chat else None
    chat = Protocol(spec=chat_protocol_spec)
    protocols = [chat]

    def for_buyer(ctx: Context, sender: str) -> bool:
        if buyer is None:
            return False
        # A seller may answer in a new session; without a sales desk, it is still a reply.
        return buyer.expects(sender, str(ctx.session)) or (
            chat_desk is None and buyer.expects(sender)
        )

    @chat.on_message(model=ChatMessage)
    async def _chat(ctx: Context, sender: str, msg: ChatMessage) -> None:
        if buyer is not None and for_buyer(ctx, sender):
            await buyer.on_chat(ctx, sender, msg)
        elif chat_desk is not None:
            await chat_desk.on_chat(ctx, sender, msg)
        else:
            await ctx.send(sender, ChatAcknowledgement(acknowledged_msg_id=msg.msg_id))

    @chat.on_message(model=ChatAcknowledgement)
    async def _ack(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
        """The other side acknowledges our messages; nothing to do."""

    if chat_desk is not None:
        selling = Protocol(spec=payment_protocol_spec, role="seller")

        @selling.on_message(model=CommitPayment)
        async def _commit(ctx: Context, sender: str, msg: CommitPayment) -> None:
            await chat_desk.on_commit(ctx, sender, msg)

        @selling.on_message(model=RejectPayment)
        async def _reject(ctx: Context, sender: str, msg: RejectPayment) -> None:
            await chat_desk.on_reject(ctx, sender, msg)

        protocols.append(selling)

    if buyer is not None:
        buying = Protocol(spec=payment_protocol_spec, role="buyer")

        @buying.on_message(model=RequestPayment)
        async def _request(ctx: Context, sender: str, msg: RequestPayment) -> None:
            await buyer.on_request_payment(ctx, sender, msg)

        @buying.on_message(model=CompletePayment)
        async def _complete(ctx: Context, sender: str, msg: CompletePayment) -> None:
            await buyer.on_complete(ctx, sender, msg)

        @buying.on_message(model=CancelPayment)
        async def _cancel(ctx: Context, sender: str, msg: CancelPayment) -> None:
            await buyer.on_cancel(ctx, sender, msg)

        protocols.append(buying)
    return protocols
