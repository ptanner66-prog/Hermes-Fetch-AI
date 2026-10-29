"""A ledger response must describe the exact transaction the bridge is settling."""

from dataclasses import replace

import pytest

from hermes_fetch_ai.ledger import LedgerUnavailable
from hermes_fetch_ai.seller import PaymentProof, PaymentRefused
from hermes_fetch_ai.store import PurchaseRefused
from tests import test_seller as seller_cases
from tests.test_buyer import BUYING_WALLET, Market
from tests.test_ledger import TX, reader, respond
from tests.test_seller import BUYER, DIGEST, pay_for, quote
from tests.test_sender import HASH, Client, Submitted, sender

clock = seller_cases.clock
ledger = seller_cases.ledger
seller = seller_cases.seller


async def test_ledger_response_hash_must_match_the_requested_transaction():
    with pytest.raises(LedgerUnavailable, match="different transaction"):
        await reader(respond(200, TX)).get_tx("AB" * 32)


def test_node_cannot_replace_the_locally_signed_transaction_hash():
    payment_sender = sender()
    submitted = Submitted(tx_hash="CD" * 32)
    try:
        outcome = payment_sender._broadcast(Client(submitted=submitted), object(), HASH)
        assert outcome.status == "unknown"
        assert outcome.tx_hash == HASH
        assert not submitted.waited
    finally:
        payment_sender.close()


async def test_call_quote_cannot_be_redeemed_through_chat(seller, ledger, clock):
    quoted, reference = quote(seller)
    tx_hash = pay_for(ledger, quoted, reference, memo="", clock_now_ms=int(clock.now * 1000))
    with pytest.raises(PaymentRefused, match="protocol"):
        await seller.redeem(
            PaymentProof(reference, tx_hash),
            sender=BUYER,
            subject="research",
            digest=DIGEST,
            kind="chat",
        )
    assert not seller.store.tx_used(tx_hash)


async def test_seller_rejects_a_reader_returning_another_transaction(seller, ledger, clock):
    quoted, reference = quote(seller)
    real_hash = pay_for(ledger, quoted, reference, clock_now_ms=int(clock.now * 1000))
    real_tx = await ledger.get_tx(real_hash)

    async def wrong_transaction(tx_hash):
        return real_tx

    ledger.get_tx = wrong_transaction
    with pytest.raises(PaymentRefused, match="different transaction"):
        await seller.redeem(
            PaymentProof(reference, "AB" * 32), sender=BUYER, subject="research", digest=DIGEST
        )
    assert not seller.store.tx_used("AB" * 32)


async def test_absent_transaction_after_an_hour_still_reserves_the_spending_budget(tmp_path):
    market = Market(tmp_path, outcome="unknown")
    try:
        _, shown = await market.quote()
        await market.approve(shown)
        market.clock.now += 3601
        review = await market.buyer.check(shown.id)
        assert review.status == "needs_review"
        assert market.buyer_store.spent_since(0) == shown.amount_base
    finally:
        market.close()


async def test_unsettled_broadcast_reserves_budget_beyond_the_daily_window(tmp_path):
    market = Market(tmp_path, outcome="unknown", max_per_day="1", max_per_seller_per_day="1")
    try:
        _, shown = await market.quote()
        await market.approve(shown)
        market.clock.now += 86_401
        since = int((market.clock.now - 86_400) * 1000)
        assert market.buyer_store.spent_since(since) == shown.amount_base
        # The quota check must reserve unknown spends, not just the status display.
        _, second = await market.quote()
        market.cfg.buying.max_per_day = "0.05"
        with pytest.raises(PurchaseRefused, match="daily limit"):
            await market.approve(second)
    finally:
        market.close()


async def test_late_payment_confirmation_counts_in_the_current_daily_budget(tmp_path):
    market = Market(tmp_path, outcome="lost")
    try:
        _, shown = await market.quote()
        await market.approve(shown)
        market.clock.now += 86_401
        await market.buyer.check(shown.id)
        since = int((market.clock.now - 86_400) * 1000)
        assert market.buyer_store.spent_since(since) == shown.amount_base
    finally:
        market.close()


@pytest.mark.parametrize("change", ["hash", "height", "payer", "memo", "amount"])
async def test_buyer_keeps_ambiguous_ledger_evidence_for_review(tmp_path, change):
    market = Market(tmp_path, outcome="lost")
    try:
        _, shown = await market.quote()
        review = await market.approve(shown)
        tx = await market.ledger.get_tx(review.tx_hash)
        if change == "hash":
            tx = replace(tx, hash="AB" * 32)
        elif change == "height":
            tx = replace(tx, height=0)
        elif change == "payer":
            tx = replace(tx, transfers=(replace(tx.transfers[0], sender=BUYING_WALLET + "x"),))
        elif change == "memo":
            tx = replace(tx, memo="another-order")
        else:
            tx = replace(tx, transfers=(replace(tx.transfers[0], amount=1),))

        async def lookup(tx_hash):
            return tx

        market.ledger.get_tx = lookup
        result = await market.buyer.check(shown.id)
        assert result.status == "needs_review"
        assert market.buyer_store.spent_since(0) == shown.amount_base
    finally:
        market.close()
