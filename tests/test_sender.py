"""Sending testnet FET: what each way a broadcast can end means for the payment."""

import hashlib
import threading

import pytest
from cosmpy.aerial.exceptions import BroadcastError, QueryTimeoutError

from hermes_fetch_ai.config import PaymentsConfig
from hermes_fetch_ai.sender import CosmpySender, SendOutcome, tx_hash_of

HASH = "AB" * 32


class Submitted:
    def __init__(self, tx_hash=HASH, wait_error=None):
        self.tx_hash = tx_hash
        self.wait_error = wait_error
        self.waited = False

    def wait_to_complete(self, timeout=None, poll_period=None):
        self.waited = True
        if self.wait_error:
            raise self.wait_error
        return self


class Client:
    def __init__(self, broadcast_error=None, submitted=None):
        self.broadcast_error = broadcast_error
        self.submitted = submitted or Submitted()

    def broadcast_tx(self, tx):
        if self.broadcast_error:
            raise self.broadcast_error
        return self.submitted


class Wallet:
    def address(self):
        return "fetch1buyingwallet"


def sender():
    return CosmpySender(Wallet(), PaymentsConfig(), inclusion_wait_seconds=0.1)


def test_the_hash_is_sha256_of_the_signed_bytes():
    assert tx_hash_of(b"tx") == hashlib.sha256(b"tx").hexdigest().upper()


@pytest.mark.parametrize(
    ("client", "expected"),
    [
        (Client(), SendOutcome("included", HASH)),
        (
            Client(broadcast_error=BroadcastError(HASH, "insufficient funds")),
            SendOutcome("rejected", HASH, "the ledger refused the payment: insufficient funds"),
        ),
        (
            Client(broadcast_error=ConnectionResetError("reset")),
            SendOutcome("unknown", HASH, "the broadcast may not have arrived: reset"),
        ),
        (
            Client(submitted=Submitted(wait_error=BroadcastError(HASH, "out of gas"))),
            SendOutcome("rejected", HASH, "the payment failed on the ledger: out of gas"),
        ),
        (
            Client(submitted=Submitted(wait_error=QueryTimeoutError())),
            SendOutcome("unknown", HASH, "the payment was not seen on the ledger in time"),
        ),
    ],
)
def test_each_broadcast_ending_has_one_meaning(client, expected):
    s = sender()
    try:
        assert s._broadcast(client, object(), HASH) == expected
    finally:
        s.close()


def test_the_hash_the_ledger_reports_wins():
    s = sender()
    try:
        outcome = s._broadcast(Client(submitted=Submitted(tx_hash="cd" * 32)), object(), HASH)
        assert outcome == SendOutcome("included", "CD" * 32)
    finally:
        s.close()


def test_a_payment_that_cannot_be_prepared_was_never_sent(monkeypatch):
    s = sender()

    def no_ledger():
        raise ConnectionError("no route to the ledger")

    monkeypatch.setattr(s, "_client", no_ledger)
    try:
        outcome = s._prepare("fetch1seller", 5, "memo")
        assert outcome == SendOutcome(
            "rejected", problem="could not prepare the payment: no route to the ledger"
        )
    finally:
        s.close()


async def test_the_hash_is_recorded_on_the_loop_before_the_broadcast(monkeypatch):
    s = sender()
    events = []
    loop_thread = threading.get_ident()
    client = Client()

    def prepare(recipient, amount, memo):
        events.append(("prepare", recipient, amount, memo))
        return client, object(), HASH

    real_broadcast = s._broadcast

    def broadcast(c, tx, tx_hash):
        events.append(("broadcast", tx_hash))
        return real_broadcast(c, tx, tx_hash)

    def record(tx_hash):
        events.append(("record", tx_hash, threading.get_ident() == loop_thread))

    monkeypatch.setattr(s, "_prepare", prepare)
    monkeypatch.setattr(s, "_broadcast", broadcast)
    try:
        outcome = await s.send(
            recipient="fetch1seller", amount_base=5, memo="ref", before_broadcast=record
        )
    finally:
        s.close()
    assert outcome.status == "included"
    assert events == [
        ("prepare", "fetch1seller", 5, "ref"),
        ("record", HASH, True),
        ("broadcast", HASH),
    ]


async def test_nothing_is_broadcast_when_recording_fails(monkeypatch):
    s = sender()
    broadcasts = []
    monkeypatch.setattr(s, "_prepare", lambda *a: (Client(), object(), HASH))
    monkeypatch.setattr(s, "_broadcast", lambda *a: broadcasts.append(a))

    def record(tx_hash):
        raise RuntimeError("the records are locked")

    try:
        with pytest.raises(RuntimeError, match="records are locked"):
            await s.send(recipient="fetch1seller", amount_base=5, memo="", before_broadcast=record)
    finally:
        s.close()
    assert broadcasts == []


async def test_a_refused_preparation_skips_recording(monkeypatch):
    s = sender()
    refused = SendOutcome("rejected", problem="could not prepare the payment: x")
    monkeypatch.setattr(s, "_prepare", lambda *a: refused)
    try:
        outcome = await s.send(
            recipient="fetch1seller",
            amount_base=5,
            memo="",
            before_broadcast=lambda h: pytest.fail("nothing to record"),
        )
    finally:
        s.close()
    assert outcome is refused


def test_the_ledger_client_uses_the_configured_rest_endpoint():
    s = CosmpySender(Wallet(), PaymentsConfig(ledger_url="http://127.0.0.1:1317"))
    try:
        client = s._client()
        network = client.network_config
        assert network.chain_id == "dorado-1" and network.url == "rest+http://127.0.0.1:1317"
        assert network.fee_denomination == "atestfet"
        assert s.address() == "fetch1buyingwallet"
    finally:
        s.close()
