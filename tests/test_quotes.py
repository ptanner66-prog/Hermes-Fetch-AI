import base64

import pytest

from hermes_fetch_ai.quotes import (
    PREFIX,
    QuoteError,
    issue_quote,
    open_quote,
    quote_key,
    request_digest,
)

KEY = quote_key("a seed that is only used by these tests, thirty-two plus")
CONTEXT = {
    "sender": "agent1qbuyer",
    "subject": "research",
    "digest": request_digest({"request": "hello"}),
    "recipient": "fetch1seller",
    "denom": "atestfet",
    "chain_id": "dorado-1",
}


def issue(**overrides):
    params = {
        "kind": "call",
        "amount_base": 50_000_000_000_000_000,
        "now_ms": 1_780_000_000_000,
        "ttl_seconds": 600,
        **CONTEXT,
        **overrides,
    }
    return issue_quote(KEY, **params)


def test_round_trip_and_short_enough_for_a_memo():
    quote, token = issue(tag=7)
    assert token.startswith(PREFIX)
    assert len(token) <= 100  # Cosmos memos allow 256 characters
    opened = open_quote(KEY, token, **CONTEXT)
    assert opened == quote
    assert opened.expires_ms == 1_780_000_000_000 + 600_000


def test_each_quote_has_a_fresh_reference():
    assert issue()[1] != issue()[1]


@pytest.mark.parametrize("field", ["sender", "subject", "digest", "recipient", "denom", "chain_id"])
def test_reference_only_works_for_the_call_it_was_issued_for(field):
    _, token = issue()
    with pytest.raises(QuoteError, match="does not match"):
        open_quote(KEY, token, **{**CONTEXT, field: CONTEXT[field] + "x"})


def test_another_bridge_cannot_open_the_reference():
    _, token = issue()
    with pytest.raises(QuoteError, match="does not match"):
        open_quote(quote_key("a different seed, also only for these tests!!"), token, **CONTEXT)


def test_tampered_amount_is_refused():
    _, token = issue()
    raw = bytearray(base64.urlsafe_b64decode(token[len(PREFIX) :] + "=="))
    raw[20] ^= 1  # inside the amount
    forged = PREFIX + base64.urlsafe_b64encode(bytes(raw)).decode().rstrip("=")
    with pytest.raises(QuoteError, match="does not match"):
        open_quote(KEY, forged, **CONTEXT)


@pytest.mark.parametrize(
    "token",
    ["", "hfq1.", "hfq1.!!!!", "hfq2." + "A" * 75, "hfq1." + "A" * 10, "x" * 200, 42],
)
def test_malformed_references_are_refused(token):
    with pytest.raises(QuoteError):
        open_quote(KEY, token, **CONTEXT)


def test_amount_and_tag_ranges_are_checked():
    with pytest.raises(ValueError):
        issue(amount_base=0)
    with pytest.raises(ValueError):
        issue(tag=70_000)


def test_request_digest_ignores_key_order():
    assert request_digest({"a": 1, "b": 2}) == request_digest({"b": 2, "a": 1})
    assert request_digest({"a": 1}) != request_digest({"a": 2})
