"""The ledger reader, against responses recorded from Fetch's Dorado testnet."""

import copy
import json
from pathlib import Path

import httpx
import pytest

from hermes_fetch_ai.ledger import (
    LcdLedgerReader,
    LedgerUnavailable,
    normalize_tx_hash,
    parse_tx,
)

FIXTURES = Path(__file__).parent / "fixtures" / "ledger"
TX = json.loads((FIXTURES / "tx_msgsend_dorado.json").read_text())
NODE_INFO = json.loads((FIXTURES / "node_info_dorado.json").read_text())
NOT_FOUND = json.loads((FIXTURES / "tx_not_found.json").read_text())
TX_HASH = "9EDD34AB91C3D45DAB43A0B2A25125519AED7EA1BB30F3D5B2D8E58F9FACB496"
BASE = "https://ledger.test"


def reader(handler, timeout=2.0):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return LcdLedgerReader(BASE, timeout, client=client)


def respond(status, body):
    def handler(request):
        return httpx.Response(status, json=body)

    return handler


def test_parse_real_dorado_transfer():
    tx = parse_tx(TX)
    assert tx.hash == TX_HASH
    assert tx.code == 0
    assert tx.height == 25557161
    assert tx.memo == ""
    assert tx.other_messages == ()
    assert tx.time_ms == 1791265151000  # 2026-10-06T05:39:11Z
    (transfer,) = tx.transfers
    assert transfer.sender == "fetch1lnnckuv69jj6qzh5mz7w4uzex9tcsjcckndw0l"
    assert transfer.recipient == "fetch1dcsuqllhyntgenx5wye3jp367vqkv7ax3dae9f"
    assert transfer.denom == "atestfet"
    assert transfer.amount == 10_000_000_000_000_000


def test_other_messages_are_reported_not_counted():
    data = copy.deepcopy(TX)
    data["tx"]["body"]["messages"].append({"@type": "/cosmos.authz.v1beta1.MsgExec", "msgs": []})
    tx = parse_tx(data)
    assert tx.other_messages == ("/cosmos.authz.v1beta1.MsgExec",)
    assert len(tx.transfers) == 1


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("tx_response"),
        lambda d: d["tx"]["body"]["messages"][0]["amount"][0].update(amount="-5"),
        lambda d: d["tx"]["body"]["messages"][0]["amount"][0].update(amount="1e18"),
        lambda d: d["tx"]["body"]["messages"][0].pop("to_address"),
        lambda d: d["tx_response"].update(txhash="nothex"),
    ],
)
def test_malformed_transactions_are_unavailable_not_trusted(mutate):
    data = copy.deepcopy(TX)
    mutate(data)
    with pytest.raises(LedgerUnavailable, match="malformed"):
        parse_tx(data)


def test_missing_block_time_is_none():
    data = copy.deepcopy(TX)
    data["tx_response"]["timestamp"] = ""
    assert parse_tx(data).time_ms is None


@pytest.mark.parametrize(
    "value",
    [TX_HASH, TX_HASH.lower(), "0x" + TX_HASH.lower(), f"  {TX_HASH}\n"],
)
def test_normalize_tx_hash(value):
    assert normalize_tx_hash(value) == TX_HASH


@pytest.mark.parametrize("value", ["", "abc", TX_HASH + "0", "Z" * 64, None])
def test_normalize_tx_hash_rejects_non_hashes(value):
    with pytest.raises(ValueError):
        normalize_tx_hash(value)


async def test_get_tx_reads_the_rest_api():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, json=TX)

    tx = await reader(handler).get_tx(TX_HASH.lower())
    assert tx is not None and tx.hash == TX_HASH
    assert seen == [f"{BASE}/cosmos/tx/v1beta1/txs/{TX_HASH}"]


async def test_unknown_transaction_is_none():
    assert await reader(respond(404, NOT_FOUND)).get_tx(TX_HASH) is None
    # Some nodes report "not found" with another status code.
    assert await reader(respond(500, NOT_FOUND)).get_tx(TX_HASH) is None


async def test_other_errors_are_unavailable():
    with pytest.raises(LedgerUnavailable):
        await reader(respond(400, {"code": 3, "message": "invalid request"})).get_tx(TX_HASH)


async def test_transient_failures_are_retried():
    answers = iter(
        [
            httpx.Response(200, content=b""),
            httpx.Response(503),
            httpx.Response(200, json=TX),
        ]
    )

    tx = await reader(lambda request: next(answers)).get_tx(TX_HASH)
    assert tx is not None


async def test_persistent_failures_give_up_within_the_deadline():
    calls = []

    def handler(request):
        calls.append(1)
        raise httpx.ConnectError("refused")

    with pytest.raises(LedgerUnavailable, match="ConnectError"):
        await reader(handler, timeout=1.0).get_tx(TX_HASH)
    assert 1 <= len(calls) <= 4


async def test_non_json_answers_are_unavailable():
    def handler(request):
        return httpx.Response(200, content=b"<html>maintenance</html>")

    with pytest.raises(LedgerUnavailable, match="not JSON"):
        await reader(handler, timeout=0.5).get_tx(TX_HASH)


async def test_chain_id_from_node_info():
    assert await reader(respond(200, NODE_INFO)).chain_id() == "dorado-1"
    with pytest.raises(LedgerUnavailable):
        await reader(respond(200, {"unexpected": True})).chain_id()


async def test_balance():
    body = {"balance": {"denom": "atestfet", "amount": "1500000000000000000"}}
    assert (
        await reader(respond(200, body)).balance("fetch1x", "atestfet") == 1_500_000_000_000_000_000
    )
    with pytest.raises(LedgerUnavailable):
        await reader(respond(404, {"code": 5})).balance("fetch1x", "atestfet")


async def test_reader_owns_and_closes_its_client():
    owned = LcdLedgerReader(BASE, 1.0)
    await owned.aclose()
    shared = httpx.AsyncClient()
    await LcdLedgerReader(BASE, 1.0, client=shared).aclose()
    assert not shared.is_closed
    await shared.aclose()
