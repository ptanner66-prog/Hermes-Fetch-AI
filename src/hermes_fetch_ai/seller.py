"""Verify payments on the ledger and turn them into credits.

Fetch's Agent Payment Protocol leaves verification to the seller. Here the
seller reads the transaction itself and accepts it only if it pays this
bridge's address, in the right denomination, at least the quoted amount
(exact integers), bound to the quote (memo, or amount tag for chat), inside
the quote's time window, and has never been used before. Nothing the buyer
says about the payment is trusted.
"""

from __future__ import annotations

import json
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .config import PaymentsConfig
from .ledger import LedgerReader, LedgerUnavailable, TxRecord, normalize_tx_hash
from .money import format_fet
from .policy import TokenBuckets
from .quotes import PREFIX, Quote, QuoteError, QuoteKind, issue_quote, open_quote
from .store import (
    Credit,
    CreditUnavailable,
    PaymentAlreadyUsed,
    QuoteAlreadyPaid,
    Store,
    credit_problem,
)

PAYMENT_REQUIRED = "payment required: "
# A payment may land slightly before the quote's clock or after its expiry.
EARLY_GRACE_MS = 30_000
LATE_GRACE_MS = 120_000
# Chat prices carry an "order code": a surcharge of 1 to 65535 billionths of a
# FET, so a payment without our memo is still tied to one order by its amount.
ORDER_CODE_UNIT = 10**9
ORDER_CODES = 2**16 - 1
# Wallets that convert amounts with floating point can be off by a little; a
# tenth of an order-code step still tells every order apart.
AMOUNT_TOLERANCE = ORDER_CODE_UNIT // 10
_MAX_TRACKED_SENDERS = 4096


class PaymentRefused(Exception):
    """The payment cannot be accepted (now); ``status`` names the kind of problem."""

    def __init__(self, reason: str, *, status: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status


@dataclass(frozen=True)
class PaymentProof:
    reference: str
    tx_hash: str


def parse_payment_terms(error: str | None) -> dict[str, Any] | None:
    """The terms in a ``payment required`` error from a bridge, or None."""
    if not error or not error.startswith(PAYMENT_REQUIRED):
        return None
    try:
        terms = json.loads(error[len(PAYMENT_REQUIRED) :])
    except ValueError:
        return None
    return terms if isinstance(terms, dict) else None


def short_tx(tx_hash: str) -> str:
    return f"{tx_hash[:8]}…{tx_hash[-4:]}" if len(tx_hash) > 12 else tx_hash


def short_reference(reference: str) -> str:
    """A loggable form of a quote reference: its tail, where the signature makes it unique."""
    return f"{PREFIX}…{reference[-10:]}"


def check_transfer(
    quote: Quote, reference: str, tx: TxRecord, *, require_memo: bool = True
) -> str | None:
    """Why ``tx`` does not pay ``quote``, or None if it does."""
    if tx.code != 0:
        return "the transaction failed on the ledger"
    if tx.height <= 0:
        return "the transaction is not in a block yet"
    if tx.other_messages:
        return "the transaction does more than a plain transfer"
    payers = {transfer.sender for transfer in tx.transfers}
    if len(payers) != 1:
        return "the transaction must have exactly one payer"
    memo = tx.memo.strip()
    if memo.startswith(PREFIX) and memo != reference:
        return "the transaction pays for a different quote"
    if require_memo and memo != reference:
        return "the transaction memo must be the quote reference"
    paid = sum(
        transfer.amount
        for transfer in tx.transfers
        if transfer.recipient == quote.recipient and transfer.denom == quote.denom
    )
    if paid == 0:
        return f"the transaction does not pay {quote.recipient} in {quote.denom}"
    if memo != reference:
        # No memo binding: the exact amount, order code included, identifies the quote.
        if abs(paid - quote.amount_base) > AMOUNT_TOLERANCE:
            return f"the amount must be exactly {format_fet(quote.amount_base)} FET without a memo"
    elif paid < quote.amount_base:
        return f"underpaid: {format_fet(paid)} FET of {format_fet(quote.amount_base)} FET"
    if tx.time_ms is None:
        return "the transaction has no block time"
    if tx.time_ms < quote.created_ms - EARLY_GRACE_MS:
        return "the transaction was made before the quote"
    if tx.time_ms > quote.expires_ms + LATE_GRACE_MS:
        return "the payment arrived after the quote expired"
    return None


class Seller:
    """Quotes, verifies payments, and tracks credits for one bridge."""

    def __init__(
        self,
        *,
        payments: PaymentsConfig,
        store: Store,
        key: bytes,
        payout: str,
        ledger_factory: Callable[[], LedgerReader],
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.payments = payments
        self.store = store
        self.payout = payout
        self._key = key
        self._ledger_factory = ledger_factory
        self._ledger: LedgerReader | None = None
        self._chain_checked = False
        self._clock = clock
        self._buckets = TokenBuckets()

    def now_ms(self) -> int:
        return int(self._clock() * 1000)

    def quote(
        self, *, kind: QuoteKind, sender: str, subject: str, digest: str, amount_base: int
    ) -> tuple[Quote, str]:
        """A signed quote for ``amount_base``; a chat quote adds a random order code."""
        tag = secrets.randbelow(ORDER_CODES) + 1 if kind == "chat" else 0
        return issue_quote(
            self._key,
            kind=kind,
            sender=sender,
            subject=subject,
            digest=digest,
            amount_base=amount_base + tag * ORDER_CODE_UNIT,
            recipient=self.payout,
            denom=self.payments.denom,
            chain_id=self.payments.chain_id,
            now_ms=self.now_ms(),
            ttl_seconds=self.payments.quote_ttl_seconds,
            tag=tag,
        )

    def payment_required(self, quote: Quote, reference: str) -> str:
        """The error text that tells a buyer what to pay and how."""
        terms = {
            "v": 1,
            "reference": reference,
            "service": quote.subject,
            "amount": format_fet(quote.amount_base),
            "currency": "FET",
            "amount_base": str(quote.amount_base),
            "denom": quote.denom,
            "recipient": quote.recipient,
            "chain_id": quote.chain_id,
            "network": self.payments.network,
            "payment_method": "fet_direct",
            "memo": reference,
            "expires_at_ms": quote.expires_ms,
        }
        return PAYMENT_REQUIRED + json.dumps(terms, sort_keys=True, separators=(",", ":"))

    async def _reader(self) -> LedgerReader:
        if self._ledger is None:
            self._ledger = self._ledger_factory()
        if not self._chain_checked:
            chain = await self._ledger.chain_id()
            if chain != self.payments.chain_id:
                raise PaymentRefused(
                    f"the ledger at {self.payments.ledger_url} is {chain!r}, "
                    f"not {self.payments.chain_id!r}; payments are off until this is fixed",
                    status="unavailable",
                )
            self._chain_checked = True
        return self._ledger

    async def redeem(
        self,
        proof: PaymentProof,
        *,
        sender: str,
        subject: str,
        digest: str,
        kind: QuoteKind = "call",
    ) -> Credit:
        """Return the credit this payment buys, verifying it on the ledger if it is new."""
        try:
            quote = open_quote(
                self._key,
                proof.reference,
                sender=sender,
                subject=subject,
                digest=digest,
                recipient=self.payout,
                denom=self.payments.denom,
                chain_id=self.payments.chain_id,
            )
        except QuoteError as exc:
            raise PaymentRefused(str(exc), status="mismatch") from None
        try:
            tx_hash = normalize_tx_hash(proof.tx_hash)
        except ValueError as exc:
            raise PaymentRefused(f"payment invalid: {exc}", status="invalid") from None
        now = self.now_ms()
        window_ms = self.payments.redeem_window_seconds * 1000
        self.store.lapse(older_than_ms=now - window_ms, now_ms=now)
        existing = self.store.credit(proof.reference)
        if existing is not None and existing.tx_hash == tx_hash:
            if existing.status != "paid":
                # "done": the request ran; its buyer may ask for the answer again.
                status = "done" if existing.status == "done" else "used"
                raise PaymentRefused(credit_problem(existing.status), status=status)
            return existing
        if self.store.tx_used(tx_hash):
            raise PaymentRefused("payment already used", status="used")
        if now > quote.expires_ms + window_ms:
            raise PaymentRefused("quote expired", status="expired")
        ok, why = self._buckets.consume(
            sender,
            "verify",
            self.payments.max_verifications_per_minute_per_sender,
            self.payments.max_global_verifications_per_minute,
            _MAX_TRACKED_SENDERS,
        )
        if not ok:
            raise PaymentRefused(f"payment pending: {why}; try again shortly", status="limited")
        try:
            ledger = await self._reader()
            tx = await ledger.get_tx(tx_hash)
        except LedgerUnavailable as exc:
            raise PaymentRefused(
                f"payment pending: {exc}; try again shortly", status="pending"
            ) from None
        if tx is None:
            raise PaymentRefused(
                "payment pending: the transaction is not on the ledger yet; try again shortly",
                status="pending",
            )
        problem = check_transfer(quote, proof.reference, tx, require_memo=kind == "call")
        if problem is not None:
            raise PaymentRefused(f"payment invalid: {problem}", status="invalid")
        payer = tx.transfers[0].sender
        try:
            return self.store.record_payment(
                reference=proof.reference,
                kind=kind,
                sender=sender,
                subject=subject,
                digest=digest,
                amount_base=quote.amount_base,
                tx_hash=tx_hash,
                payer=payer,
                block_time_ms=tx.time_ms,
                height=tx.height,
                quoted_ms=quote.created_ms,
                now_ms=self.now_ms(),
            )
        except PaymentAlreadyUsed:
            raise PaymentRefused("payment already used", status="used") from None
        except QuoteAlreadyPaid:
            raise PaymentRefused(
                "this quote was already paid by another transaction; "
                "the extra payment is recorded so the seller can refund it",
                status="used",
            ) from None

    def begin(self, credit: Credit) -> Credit:
        try:
            return self.store.begin_run(
                credit.reference, max_attempts=self.payments.max_attempts, now_ms=self.now_ms()
            )
        except CreditUnavailable as exc:
            raise PaymentRefused(exc.reason, status="used") from None

    def finish(self, credit: Credit, *, ok: bool) -> Credit:
        return self.store.finish_run(
            credit.reference, ok=ok, max_attempts=self.payments.max_attempts, now_ms=self.now_ms()
        )

    async def aclose(self) -> None:
        if self._ledger is not None:
            await self._ledger.aclose()
            self._ledger = None
        self.store.close()
