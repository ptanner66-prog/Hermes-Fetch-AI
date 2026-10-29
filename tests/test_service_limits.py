"""Admission is advisory; service budgets are enforced when execution starts."""

import asyncio

from hermes_fetch_ai.programs import ServiceResult
from tests import test_services as service_cases
from tests.test_services import call, pay_for
from tests.test_store import pay

desk = service_cases.desk
ledger = service_cases.ledger


async def test_simultaneously_admitted_free_calls_cannot_exceed_daily_limit(desk, monkeypatch):
    desk.cfg.services["free"].max_runs_per_day = 1
    admitted = asyncio.Event()
    pending = 0
    original = desk.admit

    async def admit_together(*args, **kwargs):
        nonlocal pending
        result = await original(*args, **kwargs)
        pending += 1
        if pending == 2:
            admitted.set()
        await admitted.wait()
        return result

    monkeypatch.setattr(desk, "admit", admit_together)
    results = await asyncio.wait_for(
        asyncio.gather(call(desk, "service.free"), call(desk, "service.free")), timeout=5
    )
    assert sum(not result.is_error for result in results) == 1
    assert desk.seller.store.runs_since("free", 0) == 1


async def test_paid_retry_at_daily_limit_keeps_credit_and_attempt_count(desk):
    desk.cfg.services["research"].max_runs_per_day = 1

    class FailingRunner:
        async def run(self, request):
            return ServiceResult("", ok=False, problem="failed run")

    desk.runners["research"] = FailingRunner()
    credit = pay(desk.seller.store)
    first = await desk.serve("research", credit.sender, "hello", credit, {})
    assert first.is_error
    retriable = desk.seller.store.credit(credit.reference)
    assert (retriable.status, retriable.attempts) == ("paid", 1)
    second = await desk.serve("research", credit.sender, "hello", retriable, {})
    assert second.is_error and "limit for today" in second.text
    retained = desk.seller.store.credit(credit.reference)
    assert (retained.status, retained.attempts) == ("paid", 1)
    assert desk.seller.store.runs_since("research", 0) == 1


async def test_paid_cached_answer_can_be_retrieved_at_daily_limit(desk, ledger):
    desk.cfg.services["research"].max_runs_per_day = 1
    proof = await pay_for(desk, ledger, "hello")
    first = await call(desk, "service.research", proof=proof)
    assert not first.is_error
    repeated = await call(desk, "service.research", proof=proof)
    assert not repeated.is_error
    assert repeated.text == first.text and repeated.audit["payment"] == "repeat"
    assert desk.seller.store.runs_since("research", 0) == 1

    stranger = await call(desk, "service.research", proof=proof, sender="agent1stranger")
    assert stranger.is_error and "does not match" in stranger.text
    replay = await call(
        desk, "service.research", proof=proof, remember=lambda: (False, "replay detected")
    )
    assert replay.is_error and replay.text == "replay detected"
    desk.seller.store.set_paused(True)
    paused = await call(desk, "service.research", proof=proof)
    assert paused.is_error and "not taking requests" in paused.text


def test_earnings_totals_keep_exact_amounts_beyond_sqlite_integer_range(desk):
    total = 100 * 10**18
    pay(desk.seller.store, amount=total)
    pay(desk.seller.store, reference="ref-2", tx_hash="B" * 64, amount=total)
    assert desk.seller.store.earned_since(0) == (2, total * 2)
