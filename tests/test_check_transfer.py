"""Every way a transaction can fail to pay a quote."""

import dataclasses

import pytest

from hermes_fetch_ai.ledger import Transfer, TxRecord
from hermes_fetch_ai.quotes import issue_quote, quote_key
from hermes_fetch_ai.seller import EARLY_GRACE_MS, LATE_GRACE_MS, check_transfer

NOW = 1_780_000_000_000
PRICE = 50_000_000_000_000_000
SELLER = "fetch1seller"
QUOTE, REFERENCE = issue_quote(
    quote_key("only for these tests, at least thirty-two characters"),
    kind="call",
    sender="agent1qbuyer",
    subject="research",
    digest="d" * 64,
    amount_base=PRICE,
    recipient=SELLER,
    denom="atestfet",
    chain_id="dorado-1",
    now_ms=NOW,
    ttl_seconds=600,
)


def tx(**overrides):
    base = TxRecord(
        hash="A" * 64,
        height=100,
        code=0,
        time_ms=NOW + 5_000,
        memo=REFERENCE,
        transfers=(Transfer("fetch1buyer", SELLER, "atestfet", PRICE),),
        other_messages=(),
    )
    return dataclasses.replace(base, **overrides)


def test_a_correct_payment_passes():
    assert check_transfer(QUOTE, REFERENCE, tx()) is None


def test_overpaying_is_accepted():
    assert (
        check_transfer(
            QUOTE,
            REFERENCE,
            tx(transfers=(Transfer("fetch1buyer", SELLER, "atestfet", PRICE * 2),)),
        )
        is None
    )


def test_payment_split_across_transfers_from_one_payer_counts():
    half = PRICE // 2
    split = (
        Transfer("fetch1buyer", SELLER, "atestfet", half),
        Transfer("fetch1buyer", SELLER, "atestfet", PRICE - half),
    )
    assert check_transfer(QUOTE, REFERENCE, tx(transfers=split)) is None


@pytest.mark.parametrize(
    ("overrides", "problem"),
    [
        ({"code": 5}, "failed on the ledger"),
        ({"height": 0}, "not in a block"),
        ({"other_messages": ("/cosmos.authz.v1beta1.MsgExec",)}, "more than a plain transfer"),
        ({"transfers": ()}, "exactly one payer"),
        (
            {
                "transfers": (
                    Transfer("fetch1buyer", SELLER, "atestfet", PRICE // 2),
                    Transfer("fetch1other", SELLER, "atestfet", PRICE // 2),
                )
            },
            "exactly one payer",
        ),
        ({"memo": ""}, "memo must be the quote reference"),
        ({"memo": "thanks!"}, "memo must be the quote reference"),
        ({"memo": "hfq1.someoneelsesquote"}, "pays for a different quote"),
        (
            {"transfers": (Transfer("fetch1buyer", "fetch1elsewhere", "atestfet", PRICE),)},
            "does not pay",
        ),
        ({"transfers": (Transfer("fetch1buyer", SELLER, "afet", PRICE),)}, "does not pay"),
        ({"transfers": (Transfer("fetch1buyer", SELLER, "atestfet", PRICE - 1),)}, "underpaid"),
        ({"time_ms": None}, "no block time"),
        ({"time_ms": NOW - EARLY_GRACE_MS - 1}, "before the quote"),
        ({"time_ms": QUOTE.expires_ms + LATE_GRACE_MS + 1}, "after the quote expired"),
    ],
)
def test_bad_payments_are_refused(overrides, problem):
    assert problem in check_transfer(QUOTE, REFERENCE, tx(**overrides))


def test_grace_periods_are_inclusive():
    assert check_transfer(QUOTE, REFERENCE, tx(time_ms=NOW - EARLY_GRACE_MS)) is None
    assert check_transfer(QUOTE, REFERENCE, tx(time_ms=QUOTE.expires_ms + LATE_GRACE_MS)) is None


def test_without_a_memo_only_the_exact_amount_binds_the_payment():
    exact = tx(memo="")
    assert check_transfer(QUOTE, REFERENCE, exact, require_memo=False) is None
    over = tx(memo="", transfers=(Transfer("fetch1buyer", SELLER, "atestfet", PRICE + 1),))
    assert "exactly" in check_transfer(QUOTE, REFERENCE, over, require_memo=False)
    # Even where memos are optional, another quote's reference is never accepted.
    foreign = tx(memo="hfq1.someoneelsesquote")
    assert "different quote" in check_transfer(QUOTE, REFERENCE, foreign, require_memo=False)
