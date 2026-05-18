from __future__ import annotations

import time
import uuid
from typing import Any

from uagents import Protocol
from uagents_core.contrib.protocols.payment import (
    CommitPayment,
    RejectPayment,
    payment_protocol_spec,
)

from .audit import AuditWriter
from .config import BridgeConfig
from .payments import PaymentDryRunStore


def build_payment_protocol(
    cfg: BridgeConfig, audit: AuditWriter, store: PaymentDryRunStore | None = None
) -> Protocol:
    if cfg.payment.mode != "dry_run":
        raise ValueError("payment protocol is only implemented for dry_run mode in this proof")
    payment_store = store or PaymentDryRunStore()
    proto = Protocol(spec=payment_protocol_spec, role="seller")

    @proto.on_message(model=CommitPayment)
    async def _commit(ctx: Any, sender_or_msg: Any, maybe_msg: CommitPayment | None = None) -> None:
        sender = str(sender_or_msg) if maybe_msg is not None else str(getattr(ctx, "sender", "unknown"))
        msg = maybe_msg if maybe_msg is not None else sender_or_msg
        trace_id = str(uuid.uuid4())
        start = time.perf_counter()
        response = payment_store.commit(sender, msg)
        status = "complete" if response.__class__.__name__ == "CompletePayment" else "cancel"
        audit.write(
            trace_id=trace_id,
            sender=sender,
            protocol="payment",
            msg_type="payment_commit",
            decision=status,
            reason=getattr(response, "reason", None) or "ok",
            duration_ms=int((time.perf_counter() - start) * 1000),
            payment_reference=msg.reference,
            payment_status=status,
            payment_method=msg.funds.payment_method,
            payment_currency=msg.funds.currency,
            payment_amount=msg.funds.amount,
            payment_mode=cfg.payment.mode,
            transaction_id_short=getattr(response, "transaction_id", None),
            send_status="before_send",
        )
        try:
            await ctx.send(sender, response)
        except Exception as exc:
            audit.write(
                trace_id=str(uuid.uuid4()),
                sender=sender,
                protocol="payment",
                msg_type="payment_commit",
                decision="send",
                reason=str(exc),
                error_class=exc.__class__.__name__,
                duration_ms=int((time.perf_counter() - start) * 1000),
                payment_reference=msg.reference,
                payment_status=status,
                payment_mode=cfg.payment.mode,
                send_status="failure",
            )
            raise
        audit.write(
            trace_id=str(uuid.uuid4()),
            sender=sender,
            protocol="payment",
            msg_type="payment_commit",
            decision="send",
            reason="ok",
            duration_ms=int((time.perf_counter() - start) * 1000),
            payment_reference=msg.reference,
            payment_status=status,
            payment_mode=cfg.payment.mode,
            send_status="success",
        )

    @proto.on_message(model=RejectPayment)
    async def _reject(ctx: Any, sender_or_msg: Any, maybe_msg: RejectPayment | None = None) -> None:
        sender = str(sender_or_msg) if maybe_msg is not None else str(getattr(ctx, "sender", "unknown"))
        msg = maybe_msg if maybe_msg is not None else sender_or_msg
        audit.write(
            trace_id=str(uuid.uuid4()),
            sender=sender,
            protocol="payment",
            msg_type="payment_reject",
            decision="reject",
            reason=msg.reason or "rejected by counterparty",
            payment_mode=cfg.payment.mode,
        )

    return proto
