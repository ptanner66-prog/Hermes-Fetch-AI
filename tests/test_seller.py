"""Redeeming payments: the seller verifies on the ledger and never trusts the buyer."""

import asyncio

import pytest

from hermes_fetch_ai.config import PaymentsConfig
from hermes_fetch_ai.fake_ledger import FakeLedger
from hermes_fetch_ai.ledger import LedgerUnavailable
from hermes_fetch_ai.quotes import quote_key
from hermes_fetch_ai.seller import (
    ORDER_CODE_UNIT,
    ORDER_CODES,
    PaymentProof,
    PaymentRefused,
    Seller,
    parse_payment_terms,
    short_reference,
    short_tx,
)
from hermes_fetch_ai.store import Store

PAYOUT = "fetch1hh09pm44murgmu7rpaxluwad3way3nxq0fl6fx"
BUYER = "agent1qbuyer"
PRICE = 50_000_000_000_000_000
DIGEST = "d" * 64


class Clock:
    def __init__(self, now=1_780_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


@pytest.fixture
def ledger():
    return FakeLedger()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def seller(tmp_path, ledger, clock):
    s = Seller(
        payments=PaymentsConfig(enabled=True, max_verifications_per_minute_per_sender=100),
        store=Store.open(tmp_path / "payments.sqlite3"),
        key=quote_key("only for these tests, at least thirty-two characters"),
        payout=PAYOUT,
        ledger_factory=lambda: ledger,
        clock=clock,
    )
    yield s
    s.store.close()


def quote(seller, sender=BUYER, digest=DIGEST):
    return seller.quote(
        kind="call", sender=sender, subject="research", digest=digest, amount_base=PRICE
    )


def pay_for(ledger, quote_, reference, *, amount=None, memo=None, clock_now_ms=None):
    return ledger.pay(
        payer="fetch1buyerwallet",
        recipient=quote_.recipient,
        amount_base=quote_.amount_base if amount is None else amount,
        memo=reference if memo is None else memo,
        time_ms=clock_now_ms,
    )


async def redeem(seller, reference, tx_hash, sender=BUYER, digest=DIGEST):
    return await seller.redeem(
        PaymentProof(reference, tx_hash), sender=sender, subject="research", digest=digest
    )


def test_payment_required_terms_are_complete_and_parseable(seller):
    q, ref = quote(seller)
    terms = parse_payment_terms(seller.payment_required(q, ref))
    assert terms == {
        "v": 1,
        "reference": ref,
        "service": "research",
        "amount": "0.05",
        "currency": "FET",
        "amount_base": str(PRICE),
        "denom": "atestfet",
        "recipient": PAYOUT,
        "chain_id": "dorado-1",
        "network": "testnet",
        "payment_method": "fet_direct",
        "memo": ref,
        "expires_at_ms": q.expires_ms,
    }


@pytest.mark.parametrize(
    "error", [None, "", "tool denied", "payment required: not json", "payment required: [1]"]
)
def test_parse_payment_terms_ignores_other_errors(error):
    assert parse_payment_terms(error) is None


async def test_valid_payment_becomes_a_credit_once(seller, ledger, clock):
    q, ref = quote(seller)
    tx_hash = pay_for(ledger, q, ref, clock_now_ms=int(clock.now * 1000))
    credit = await redeem(seller, ref, tx_hash.lower())
    assert credit.status == "paid" and credit.payer == "fetch1buyerwallet"
    # The same proof again (a retry) returns the same credit without re-verifying.
    before = ledger.requests
    assert (await redeem(seller, ref, tx_hash)).reference == ref
    assert ledger.requests == before
    # The same transaction for another quote is refused.
    _, ref2 = quote(seller, digest="e" * 64)
    with pytest.raises(PaymentRefused, match="already used"):
        await redeem(seller, ref2, tx_hash, digest="e" * 64)


async def test_reference_is_bound_to_buyer_and_request(seller, ledger, clock):
    q, ref = quote(seller)
    tx_hash = pay_for(ledger, q, ref, clock_now_ms=int(clock.now * 1000))
    with pytest.raises(PaymentRefused, match="does not match") as stolen:
        await redeem(seller, ref, tx_hash, sender="agent1qthief")
    assert stolen.value.status == "mismatch"
    with pytest.raises(PaymentRefused, match="does not match"):
        await redeem(seller, ref, tx_hash, digest="f" * 64)


async def test_ledger_failures_are_retryable(seller, ledger, clock):
    _, ref = quote(seller)
    with pytest.raises(PaymentRefused, match="payment pending") as pending:
        await redeem(seller, ref, "A" * 64)
    assert pending.value.status == "pending"

    async def broken(tx_hash):
        raise LedgerUnavailable("node is down")

    ledger.get_tx = broken
    with pytest.raises(PaymentRefused, match="payment pending: node is down"):
        await redeem(seller, ref, "B" * 64)


async def test_wrong_chain_turns_payments_off(tmp_path, clock):
    seller = Seller(
        payments=PaymentsConfig(enabled=True),
        store=Store.open(tmp_path / "p.sqlite3"),
        key=quote_key("only for these tests, at least thirty-two characters"),
        payout=PAYOUT,
        ledger_factory=lambda: FakeLedger(chain_id="fetchhub-4"),
        clock=clock,
    )
    _, ref = quote(seller)
    with pytest.raises(PaymentRefused, match="not 'dorado-1'"):
        await redeem(seller, ref, "A" * 64)
    await seller.aclose()


async def test_invalid_payments_are_refused(seller, ledger, clock):
    q, ref = quote(seller)
    now_ms = int(clock.now * 1000)
    underpaid = pay_for(ledger, q, ref, amount=PRICE - 1, clock_now_ms=now_ms)
    with pytest.raises(PaymentRefused, match="payment invalid: underpaid") as exc:
        await redeem(seller, ref, underpaid)
    assert exc.value.status == "invalid"
    no_memo = pay_for(ledger, q, ref, memo="", clock_now_ms=now_ms)
    with pytest.raises(PaymentRefused, match="memo"):
        await redeem(seller, ref, no_memo)
    with pytest.raises(PaymentRefused, match="64 hex"):
        await redeem(seller, ref, "not-a-hash")
    # Refused payments are not recorded, so nothing is used up.
    assert not seller.store.tx_used(underpaid.upper())


async def test_quotes_expire_after_the_redeem_window(seller, ledger, clock):
    q, ref = quote(seller)
    tx_hash = pay_for(ledger, q, ref, clock_now_ms=int(clock.now * 1000))
    clock.now += q.ttl_seconds + seller.payments.redeem_window_seconds + 1
    with pytest.raises(PaymentRefused, match="quote expired"):
        await redeem(seller, ref, tx_hash)


async def test_second_payment_for_a_quote_is_kept_for_refund(seller, ledger, clock):
    q, ref = quote(seller)
    now_ms = int(clock.now * 1000)
    first = pay_for(ledger, q, ref, clock_now_ms=now_ms)
    await redeem(seller, ref, first)
    second = pay_for(ledger, q, ref, clock_now_ms=now_ms + 1)
    with pytest.raises(PaymentRefused, match="refund"):
        await redeem(seller, ref, second)
    assert seller.store.used_transaction(second).disposition == "duplicate"


async def test_used_credits_are_refused(seller, ledger, clock):
    q, ref = quote(seller)
    tx_hash = pay_for(ledger, q, ref, clock_now_ms=int(clock.now * 1000))
    credit = seller.begin(await redeem(seller, ref, tx_hash))
    seller.finish(credit, ok=True)
    with pytest.raises(PaymentRefused, match="already used for a completed request"):
        await redeem(seller, ref, tx_hash)
    with pytest.raises(PaymentRefused, match="already used"):
        seller.begin(credit)


async def test_verification_is_rate_limited(tmp_path, ledger, clock):
    seller = Seller(
        payments=PaymentsConfig(enabled=True, max_verifications_per_minute_per_sender=1),
        store=Store.open(tmp_path / "p.sqlite3"),
        key=quote_key("only for these tests, at least thirty-two characters"),
        payout=PAYOUT,
        ledger_factory=lambda: ledger,
        clock=clock,
    )
    _, ref = quote(seller)
    with pytest.raises(PaymentRefused, match="not on the ledger"):
        await redeem(seller, ref, "A" * 64)
    with pytest.raises(PaymentRefused, match="rate limit") as limited:
        await redeem(seller, ref, "B" * 64)
    assert limited.value.status == "limited"
    await seller.aclose()


def test_short_references_tell_quotes_apart(seller):
    _, first = quote(seller)
    _, second = quote(seller, digest="e" * 64)
    assert short_reference(first) != short_reference(second)
    assert short_reference(first) == "hfq1.…" + first[-10:]


def test_short_forms_do_not_trip_redaction():
    from hermes_fetch_ai._redaction import redact_text

    reference = "hfq1." + "A" * 75
    tx_hash = "9EDD34AB91C3D45DAB43A0B2A25125519AED7EA1BB30F3D5B2D8E58F9FACB496"
    assert redact_text(short_reference(reference)) == short_reference(reference)
    assert redact_text(short_tx(tx_hash)) == "9EDD34AB…B496"
    assert short_tx("ABC") == "ABC"


@pytest.mark.parametrize(
    ("same_quote", "reason"),
    [(True, "payment already used"), (False, "the transaction pays for a different quote")],
)
async def test_racing_redeems_of_one_payment_make_one_credit(
    seller, ledger, clock, same_quote, reason
):
    q, ref = quote(seller)
    tx_hash = pay_for(ledger, q, ref, clock_now_ms=int(clock.now * 1000))
    other_ref = ref if same_quote else quote(seller, digest="e" * 64)[1]
    real_get_tx = ledger.get_tx

    async def slow_get_tx(tx):
        await asyncio.sleep(0)  # let the other redeem pass its checks too
        return await real_get_tx(tx)

    ledger.get_tx = slow_get_tx
    results = await asyncio.gather(
        redeem(seller, ref, tx_hash),
        redeem(seller, other_ref, tx_hash, digest=DIGEST if same_quote else "e" * 64),
        return_exceptions=True,
    )
    refused = [r for r in results if isinstance(r, PaymentRefused)]
    assert len(refused) == 1 and reason in refused[0].reason
    assert len(seller.store.credits()) == 1


def test_chat_quotes_carry_an_order_code(seller):
    amounts = set()
    for _ in range(20):
        q, _ = seller.quote(
            kind="chat", sender=BUYER, subject="research", digest=DIGEST, amount_base=PRICE
        )
        assert 1 <= q.tag <= ORDER_CODES
        assert q.amount_base == PRICE + q.tag * ORDER_CODE_UNIT
        amounts.add(q.amount_base)
    assert len(amounts) > 1  # random codes tell orders apart
    call, _ = quote(seller)
    assert (call.tag, call.amount_base) == (0, PRICE)  # MCP calls bind by memo instead
