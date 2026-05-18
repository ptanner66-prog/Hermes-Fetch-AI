from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

from uagents_core.contrib.protocols.payment import (
    CancelPayment,
    CommitPayment,
    CompletePayment,
    Funds,
    RejectPayment,
    RequestPayment,
)

from .config import BridgeConfig, PaymentFundsConfig
from .payment_policy import accepted_funds_for_tool
from .policy import normalize_tool_name

PaymentStatus = Literal["requested", "committed", "completed", "cancelled", "rejected"]


@dataclass
class PaymentRecord:
    reference: str
    sender: str
    tool: str
    accepted_funds: list[Funds]
    recipient: str
    deadline_seconds: int
    created_at: float
    status: PaymentStatus = "requested"
    transaction_id_short: str | None = None


@dataclass
class PaymentDryRunStore:
    records: dict[str, PaymentRecord] = field(default_factory=dict)
    transactions: set[str] = field(default_factory=set)

    def request(self, cfg: BridgeConfig, sender: str, tool: str, bridge_address: str) -> RequestPayment:
        if cfg.payment.mode != "dry_run":
            raise ValueError("PaymentDryRunStore only supports payment.mode=dry_run")
        safe_tool = normalize_tool_name(tool)
        funds = [_to_funds(f) for f in accepted_funds_for_tool(cfg, safe_tool)]
        if not funds:
            raise ValueError("payment required but no accepted funds are configured")
        nonce = uuid.uuid4().hex
        reference = build_reference(sender, safe_tool, nonce)
        recipient = cfg.payment.recipient or bridge_address
        self.records[reference] = PaymentRecord(
            reference=reference,
            sender=sender,
            tool=safe_tool,
            accepted_funds=funds,
            recipient=recipient,
            deadline_seconds=cfg.payment.deadline_seconds,
            created_at=time.time(),
        )
        return RequestPayment(
            accepted_funds=funds,
            recipient=recipient,
            deadline_seconds=cfg.payment.deadline_seconds,
            reference=reference,
            description=f"Dry-run payment quote for {safe_tool}",
            metadata={"mode": cfg.payment.mode, "tool": safe_tool, "nonce": nonce},
        )

    def commit(self, sender: str, msg: CommitPayment) -> CompletePayment | CancelPayment:
        tx_short = _short_tx(msg.transaction_id)
        if not msg.reference or msg.reference not in self.records:
            return CancelPayment(transaction_id=tx_short, reason="dryrun unknown payment reference")
        record = self.records[msg.reference]
        if sender != record.sender:
            return CancelPayment(transaction_id=tx_short, reason="sender does not match payment quote")
        if record.status != "requested":
            return CancelPayment(transaction_id=tx_short, reason=f"payment already {record.status}")
        if time.time() - record.created_at > record.deadline_seconds:
            record.status = "cancelled"
            return CancelPayment(transaction_id=tx_short, reason="payment quote expired")
        if not msg.transaction_id.startswith("dryrun-"):
            return CancelPayment(
                transaction_id=tx_short,
                reason="dry_run mode accepts only dryrun-* transaction ids",
            )
        if msg.transaction_id in self.transactions:
            return CancelPayment(transaction_id=tx_short, reason="duplicate dry-run transaction id")
        if msg.recipient != record.recipient:
            return CancelPayment(transaction_id=tx_short, reason="recipient does not match payment quote")
        if not _funds_match(msg.funds, record.accepted_funds):
            return CancelPayment(transaction_id=tx_short, reason="funds do not match accepted quote")
        record.status = "committed"
        record.transaction_id_short = tx_short
        self.transactions.add(msg.transaction_id)
        record.status = "completed"
        return CompletePayment(transaction_id=record.transaction_id_short)

    def reject(self, reference: str | None, reason: str | None = None) -> RejectPayment:
        if reference and reference in self.records:
            self.records[reference].status = "rejected"
        return RejectPayment(reason=reason or "payment rejected")

    def cancel(self, reference: str | None, reason: str | None = None) -> CancelPayment:
        if reference and reference in self.records:
            self.records[reference].status = "cancelled"
        return CancelPayment(reason=reason or "payment cancelled")


def _to_funds(funds: PaymentFundsConfig) -> Funds:
    return Funds(
        amount=funds.amount,
        currency=funds.currency,
        payment_method=funds.payment_method,
    )


def _funds_match(offered: Funds, accepted: list[Funds]) -> bool:
    return any(
        offered.amount == f.amount
        and offered.currency == f.currency
        and offered.payment_method == f.payment_method
        for f in accepted
    )


def build_reference(sender: str, tool: str, nonce: str) -> str:
    material = json.dumps(
        {"sender": sender, "tool": tool, "nonce": nonce}, sort_keys=True
    ).encode("utf-8")
    return "hfa-" + hashlib.sha256(material).hexdigest()[:24]


def dryrun_transaction_id() -> str:
    return "dryrun-" + uuid.uuid4().hex[:24]


def _short_tx(tx: str | None) -> str | None:
    if not tx:
        return None
    return tx[:18]
