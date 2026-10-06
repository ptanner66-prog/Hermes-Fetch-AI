import os
import stat

import pytest

from hermes_fetch_ai.store import (
    CreditUnavailable,
    PaymentAlreadyUsed,
    QuoteAlreadyPaid,
    Store,
)


@pytest.fixture
def store(tmp_path):
    s = Store.open(tmp_path / "state" / "payments.sqlite3")
    yield s
    s.close()


def pay(store, reference="ref-1", tx_hash="A" * 64, amount=10**18, now_ms=1_000):
    return store.record_payment(
        reference=reference,
        kind="call",
        sender="agent1qbuyer",
        subject="research",
        digest="d",
        amount_base=amount,
        tx_hash=tx_hash,
        payer="fetch1buyer",
        block_time_ms=now_ms - 10,
        height=7,
        quoted_ms=now_ms - 100,
        now_ms=now_ms,
    )


def test_payment_becomes_a_credit(store):
    credit = pay(store, amount=1500 * 10**18)  # beyond int64, stored exactly
    assert credit.status == "paid"
    assert credit.amount_base == 1500 * 10**18
    assert store.tx_used("A" * 64)
    assert store.credit("ref-1") == credit
    used = store.used_transaction("A" * 64)
    assert used is not None and used.disposition == "applied"
    assert store.used_transaction("B" * 64) is None


def test_a_transaction_pays_only_once(store):
    pay(store)
    with pytest.raises(PaymentAlreadyUsed):
        pay(store, reference="ref-2")
    assert store.credit("ref-2") is None


def test_a_second_payment_for_a_paid_quote_is_kept_for_a_refund(store):
    pay(store)
    with pytest.raises(QuoteAlreadyPaid):
        pay(store, tx_hash="B" * 64)
    assert store.used_transaction("B" * 64).disposition == "duplicate"
    assert store.credit("ref-1").tx_hash == "A" * 64
    (extra,) = store.extra_payments()
    assert (extra.tx_hash, extra.reference, extra.payer) == ("B" * 64, "ref-1", "fetch1buyer")


def test_run_lifecycle_success(store):
    pay(store)
    running = store.begin_run("ref-1", max_attempts=3, now_ms=2_000)
    assert (running.status, running.attempts) == ("running", 1)
    with pytest.raises(CreditUnavailable, match="already running"):
        store.begin_run("ref-1", max_attempts=3, now_ms=2_001)
    assert store.finish_run("ref-1", ok=True, max_attempts=3, now_ms=3_000).status == "done"
    with pytest.raises(CreditUnavailable, match="already used"):
        store.begin_run("ref-1", max_attempts=3, now_ms=4_000)


def test_failed_runs_can_be_retried_until_the_limit(store):
    pay(store)
    for attempt in (1, 2):
        store.begin_run("ref-1", max_attempts=3, now_ms=attempt)
        assert store.finish_run("ref-1", ok=False, max_attempts=3, now_ms=attempt).status == "paid"
    store.begin_run("ref-1", max_attempts=3, now_ms=3)
    assert store.finish_run("ref-1", ok=False, max_attempts=3, now_ms=3).status == "failed"
    with pytest.raises(CreditUnavailable, match="refund"):
        store.begin_run("ref-1", max_attempts=3, now_ms=4)


def test_attempt_limit_is_enforced_when_lowered(store):
    pay(store)
    store.begin_run("ref-1", max_attempts=3, now_ms=1)
    store.finish_run("ref-1", ok=False, max_attempts=3, now_ms=1)
    with pytest.raises(CreditUnavailable, match="refund"):
        store.begin_run("ref-1", max_attempts=1, now_ms=2)
    assert store.credit("ref-1").status == "failed"


def test_unknown_and_not_running_credits(store):
    with pytest.raises(CreditUnavailable, match="no payment"):
        store.begin_run("missing", max_attempts=3, now_ms=1)
    pay(store)
    with pytest.raises(CreditUnavailable, match="not running"):
        store.finish_run("ref-1", ok=True, max_attempts=3, now_ms=1)


def test_interrupted_runs_are_retryable_after_a_restart(tmp_path):
    path = tmp_path / "payments.sqlite3"
    store = Store.open(path)
    pay(store)
    store.begin_run("ref-1", max_attempts=3, now_ms=2)
    store.close()
    reopened = Store.open(path)
    try:
        assert reopened.credit("ref-1").status == "paid"
        assert reopened.tx_used("A" * 64)
    finally:
        reopened.close()


def test_unused_credits_lapse(store):
    pay(store, now_ms=1_000)
    pay(store, reference="ref-2", tx_hash="B" * 64, now_ms=5_000)
    assert store.lapse(older_than_ms=2_000, now_ms=6_000) == 1
    assert store.credit("ref-1").status == "lapsed"
    assert store.credit("ref-2").status == "paid"
    with pytest.raises(CreditUnavailable, match="redeem window"):
        store.begin_run("ref-1", max_attempts=3, now_ms=7_000)


def test_refunds_are_recorded(store):
    pay(store)
    assert store.mark_refunded("ref-1", now_ms=9).status == "refunded"
    with pytest.raises(CreditUnavailable):
        store.mark_refunded("ref-1", now_ms=10)
    with pytest.raises(CreditUnavailable, match="refunded"):
        store.begin_run("ref-1", max_attempts=3, now_ms=11)


def test_credit_listing(store):
    pay(store, now_ms=1)
    pay(store, reference="ref-2", tx_hash="B" * 64, now_ms=2)
    store.begin_run("ref-2", max_attempts=3, now_ms=3)
    assert [c.reference for c in store.credits()] == ["ref-2", "ref-1"]
    assert [c.reference for c in store.credits("paid")] == ["ref-1"]


def test_runs_are_counted_per_service_per_day(store):
    for t in (1, 2, 3):
        store.record_run(subject="research", sender="a", now_ms=t)
    store.record_run(subject="review", sender="a", now_ms=3)
    assert store.runs_since("research", 2) == 2
    assert store.runs_since("review", 0) == 1


def test_owner_controls(store):
    assert not store.paused()
    store.set_paused(True)
    assert store.paused()
    store.set_paused(False)
    assert not store.paused()
    store.ban("agent1qspam", reason="spam", now_ms=1)
    store.ban("agent1qspam", reason="still spam", now_ms=2)
    assert store.is_banned("agent1qspam")
    assert store.banned() == [("agent1qspam", "still spam")]
    assert store.unban("agent1qspam")
    assert not store.unban("agent1qspam")


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
def test_state_directory_is_private(store):
    assert stat.S_IMODE(store.path.parent.stat().st_mode) == 0o700


def test_newer_schema_is_refused(tmp_path):
    path = tmp_path / "payments.sqlite3"
    Store.open(path).close()
    import sqlite3

    conn = sqlite3.connect(path)
    conn.execute("PRAGMA user_version = 99")
    conn.close()
    with pytest.raises(RuntimeError, match="newer hermes-fetch-ai"):
        Store.open(path)


def test_two_bridges_sharing_a_store_cannot_both_use_a_payment(tmp_path):
    # Two processes on one state directory: SQLite's write lock serializes them.
    first = Store.open(tmp_path / "state" / "payments.sqlite3")
    second = Store.open(tmp_path / "state" / "payments.sqlite3")
    try:
        pay(first)
        with pytest.raises(PaymentAlreadyUsed):
            pay(second, reference="ref-2")
        assert second.credit("ref-1").status == "paid" and second.credit("ref-2") is None
    finally:
        first.close()
        second.close()


def test_unused_credit_finds_a_paid_credit_for_the_same_buyer_and_request(store):
    assert store.unused_credit(sender="agent1qbuyer", subject="research", digest="d") is None
    pay(store, reference="ref-old", tx_hash="A" * 64, now_ms=1_000)
    pay(store, reference="ref-new", tx_hash="B" * 64, now_ms=2_000)
    found = store.unused_credit(sender="agent1qbuyer", subject="research", digest="d")
    assert found is not None and found.reference == "ref-old"
    store.begin_run("ref-old", max_attempts=3, now_ms=3_000)
    found = store.unused_credit(sender="agent1qbuyer", subject="research", digest="d")
    assert found is not None and found.reference == "ref-new"
    assert store.unused_credit(sender="agent1qother", subject="research", digest="d") is None
    assert store.unused_credit(sender="agent1qbuyer", subject="other", digest="d") is None
