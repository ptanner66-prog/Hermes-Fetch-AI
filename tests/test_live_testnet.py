"""Live tests on Fetch's Dorado testnet. Opt-in: never part of the default run.

    HERMES_FETCH_LIVE_TESTNET=1 pytest tests/test_live_testnet.py

They use the internet: Fetch's testnet REST endpoint and faucet, and
agentverse.ai. The test FET (free, worth nothing) comes from Fetch's faucet
into a wallet made for the run, unless HERMES_FETCH_PAYER_SEED names a funded
one, whose buying wallet (key index 1) then pays. A run spends about 0.06 test
FET. HERMES_FETCH_LIVE_AGENTVERSE_API_KEY, if set, is sent with the Agentverse
search (it works without one).

They check what the hermetic tests can only simulate: Dorado's REST answers
still parse; a payment the bridge sends is on the ledger as it recorded it; a
running bridge sells a paid call for real test FET and refuses a stranger, an
underpayment, a wrong memo, and, after a restart, the same payment again; a
buying bridge buys from a selling one through the chat and payment protocols;
and Agentverse's search still answers in the shape the bridge reads.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from uagents.communication import send_sync_message
from uagents.crypto import Identity
from uagents.dispatch import dispatcher
from uagents.resolver import RulesBasedResolver
from uagents_adapter.mcp.protocol import CallTool, CallToolResponse

from hermes_fetch_ai.agent_search import search_agents
from hermes_fetch_ai.buy_demo import _until, buy_demo_config
from hermes_fetch_ai.chat_demo import chat_demo_config
from hermes_fetch_ai.config import PaymentsConfig
from hermes_fetch_ai.direct_protocol import replay_args
from hermes_fetch_ai.ledger import LcdLedgerReader
from hermes_fetch_ai.money import parse_fet
from hermes_fetch_ai.seller import parse_payment_terms
from hermes_fetch_ai.sender import CosmpySender, SendOutcome
from hermes_fetch_ai.store import Store
from hermes_fetch_ai.uagent_app import (
    build_agent,
    build_buyer,
    build_service_desk,
    payment_store_path,
)
from hermes_fetch_ai.wallet import BUYING_WALLET_INDEX, wallet_address, wallet_for

from .test_serve_http_roundtrip import _wait_for_port

LIVE_VAR = "HERMES_FETCH_LIVE_TESTNET"
PAYER_SEED_VAR = "HERMES_FETCH_PAYER_SEED"
AGENTVERSE_KEY_VAR = "HERMES_FETCH_LIVE_AGENTVERSE_API_KEY"

pytestmark = [
    pytest.mark.network,
    pytest.mark.skipif(
        os.environ.get(LIVE_VAR) != "1",
        reason=f"live testnet tests are opt-in: set {LIVE_VAR}=1",
    ),
]

PAYMENTS = PaymentsConfig()  # Fetch's Dorado testnet, as a bridge uses it by default
NEEDED = parse_fet("0.1")  # payments of about 0.06 test FET, plus fees
SERVICE_PRICE = "0.001"


def reader() -> LcdLedgerReader:
    return LcdLedgerReader(PAYMENTS.ledger_url, PAYMENTS.ledger_timeout_seconds)


async def balance_of(address: str) -> int:
    ledger = reader()
    try:
        return await ledger.balance(address, PAYMENTS.denom)
    finally:
        await ledger.aclose()


async def funded(address: str, at_least: int, timeout: float = 120.0) -> int:
    deadline = time.monotonic() + timeout
    while True:
        balance = await balance_of(address)
        if balance >= at_least or time.monotonic() > deadline:
            return balance
        await asyncio.sleep(3)


@pytest.fixture(scope="module")
def payer_seed() -> str:
    """A seed whose buying wallet holds enough test FET for the run."""
    seed = os.environ.get(PAYER_SEED_VAR) or "hermes-fetch-ai live test " + secrets.token_hex(16)
    address = wallet_address(seed, BUYING_WALLET_INDEX)
    if asyncio.run(balance_of(address)) < NEEDED:
        from cosmpy.aerial.config import NetworkConfig
        from cosmpy.aerial.faucet import FaucetApi

        FaucetApi(NetworkConfig.fetchai_stable_testnet()).get_wealth(address)
        balance = asyncio.run(funded(address, NEEDED))
        assert balance >= NEEDED, f"the faucet left {address} with {balance} atestfet"
    return seed


async def pay(seed: str, recipient: str, amount_base: int, memo: str) -> SendOutcome:
    """Send test FET from the buying wallet of ``seed``, the way a buying bridge does."""
    sender = CosmpySender(wallet_for(seed, BUYING_WALLET_INDEX), PAYMENTS)
    recorded: list[str] = []
    try:
        outcome = await sender.send(
            recipient=recipient,
            amount_base=amount_base,
            memo=memo,
            before_broadcast=recorded.append,
        )
    finally:
        sender.close()
    assert outcome.status == "included", outcome
    assert recorded == [outcome.tx_hash]  # recorded before it left the machine
    return outcome


# -- the ledger -----------------------------------------------------------------------------


async def test_the_ledger_is_dorado_and_making_blocks():
    ledger = reader()
    try:
        assert await ledger.chain_id() == "dorado-1"
        newest = await ledger.latest_block_ms()
        assert abs(time.time() * 1000 - newest) < 120_000, "Dorado has made no block for 2 minutes"
        assert (
            await ledger.balance(wallet_address("hermes-fetch-ai unused " + "x" * 32), "atestfet")
            == 0
        )
    finally:
        await ledger.aclose()


async def test_a_payment_the_bridge_sends_is_on_the_ledger_as_recorded(payer_seed):
    recipient = wallet_address("hermes-fetch-ai live recipient " + secrets.token_hex(16))
    memo = "hermes-fetch-ai live test " + secrets.token_hex(4)
    outcome = await pay(payer_seed, recipient, 1000, memo)
    ledger = reader()
    try:
        tx = await ledger.get_tx(outcome.tx_hash)
    finally:
        await ledger.aclose()
    assert tx is not None and tx.code == 0 and tx.height > 0
    assert tx.memo == memo and not tx.other_messages
    payer = wallet_address(payer_seed, BUYING_WALLET_INDEX)
    assert [(t.sender, t.recipient, t.denom, t.amount) for t in tx.transfers] == [
        (payer, recipient, "atestfet", 1000)
    ]


# -- selling over MCP calls -----------------------------------------------------------------


def start_seller(state: Path, port: int, seed: str) -> subprocess.Popen[str]:
    config = state / "seller.yaml"
    config.write_text(
        "version: 1\n"
        "agent:\n"
        "  name: hermes_live_seller\n"
        f"  port: {port}\n"
        f"  endpoint: http://127.0.0.1:{port}/submit\n"
        "  mode: endpoint\n"
        "  publish_manifest: false\n"
        "  enable_agent_inspector: false\n"
        "hermes_mcp:\n"
        "  mode: fake\n"
        "payments:\n"
        "  enabled: true\n"
        f"  state_dir: {json.dumps(str(state / 'records'))}\n"
        "services:\n"
        "  echo:\n"
        "    title: Echo\n"
        "    description: Sends the request back.\n"
        f'    price: "{SERVICE_PRICE}"\n'
        "    runner: {type: echo}\n"
        "logging:\n"
        f"  audit_path: {json.dumps(str(state / 'audit.jsonl'))}\n",
        encoding="utf-8",
    )
    env = {**os.environ, "UAGENT_" + "SEED": seed}
    process = subprocess.Popen(
        [sys.executable, "-m", "hermes_fetch_ai.cli", "serve", "--config", str(config)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_for_port(port)
    except BaseException:
        process.kill()
        process.wait(timeout=10)
        raise
    return process


def stop(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


@pytest.fixture
def seller_seed() -> str:
    return "hermes-fetch-ai live seller " + secrets.token_hex(16)


@pytest.fixture
def seller(tmp_path: Path, unused_tcp_port: int, seller_seed: str) -> Iterator[dict[str, Any]]:
    running = {"process": start_seller(tmp_path, unused_tcp_port, seller_seed)}
    try:
        yield {
            "running": running,
            "address": Identity.from_seed(seller_seed, 0).address,
            "endpoint": f"http://127.0.0.1:{unused_tcp_port}/submit",
            "restart": lambda: _restart(running, tmp_path, unused_tcp_port, seller_seed),
        }
    finally:
        stop(running["process"])


def _restart(running: dict[str, Any], state: Path, port: int, seed: str) -> None:
    stop(running["process"])
    running["process"] = start_seller(state, port, seed)


async def test_a_running_bridge_sells_a_paid_call_for_real_test_fet(payer_seed, seller):
    buyer = Identity.from_seed(payer_seed, 0)
    stranger = Identity.from_seed("hermes-fetch-ai live stranger " + secrets.token_hex(16), 0)
    resolver = RulesBasedResolver({seller["address"]: seller["endpoint"]})

    async def call(sender: Identity, request: str, proof: dict[str, str] | None = None):
        reply = await send_sync_message(
            seller["address"],
            CallTool(tool="service.echo", args=replay_args({"request": request}, payment=proof)),
            response_type=CallToolResponse,
            sender=sender,
            resolver=resolver,
            timeout=30,
        )
        assert isinstance(reply, CallToolResponse), reply
        return reply

    async def until_verified(sender: Identity, request: str, proof: dict[str, str]):
        for delay in (0, 2, 4, 8, 16):
            await asyncio.sleep(delay)
            reply = await call(sender, request, proof)
            if not (reply.error or "").startswith("payment pending"):
                return reply
        return reply

    async def quote(request: str) -> dict[str, Any]:
        reply = await call(buyer, request)
        assert (reply.error or "").startswith("payment required:"), reply
        terms = parse_payment_terms(reply.error)
        assert terms is not None, reply
        assert terms["network"] == "testnet" and terms["denom"] == "atestfet"
        assert int(terms["amount_base"]) == parse_fet(SERVICE_PRICE)
        return terms

    # Paid: the service runs once, and the buyer can collect the answer again.
    request = "live test " + secrets.token_hex(4)
    terms = await quote(request)
    sent = await pay(payer_seed, terms["recipient"], int(terms["amount_base"]), terms["memo"])
    proof = {"reference": terms["reference"], "tx_hash": sent.tx_hash}
    paid = await until_verified(buyer, request, proof)
    assert paid.error is None and request in (paid.result or ""), paid
    again = await call(buyer, request, proof)
    assert again.error is None and again.result == paid.result
    # A stranger who copies the payment from the public ledger gets nothing.
    stolen = await call(stranger, request, proof)
    assert stolen.result is None and "does not match" in (stolen.error or ""), stolen

    # One atestfet short, and the right amount with the wrong memo: both refused.
    terms = await quote("underpaid " + request)
    short = await pay(payer_seed, terms["recipient"], int(terms["amount_base"]) - 1, terms["memo"])
    refused = await until_verified(
        buyer, "underpaid " + request, {"reference": terms["reference"], "tx_hash": short.tx_hash}
    )
    assert (refused.error or "").startswith("payment invalid"), refused
    terms = await quote("wrong memo " + request)
    wrong = await pay(
        payer_seed, terms["recipient"], int(terms["amount_base"]), "not the reference"
    )
    refused = await until_verified(
        buyer, "wrong memo " + request, {"reference": terms["reference"], "tx_hash": wrong.tx_hash}
    )
    assert (refused.error or "").startswith("payment invalid"), refused

    # After a restart the kept answer is gone, and the payment is still used up.
    seller["restart"]()
    replayed = await call(buyer, request, proof)
    assert replayed.result is None and "already used" in (replayed.error or ""), replayed


# -- buying through chat --------------------------------------------------------------------


async def test_a_buying_bridge_buys_from_a_selling_bridge_through_chat(payer_seed, tmp_path):
    seller_cfg = chat_demo_config(tmp_path / "seller")  # verifies payments on Dorado itself
    seller_seed = seller_cfg.effective_seed()
    desk = build_service_desk(seller_cfg, seller_seed)
    seller = build_agent(seller_cfg, None, seed=seller_seed, desk=desk)

    buyer_cfg = buy_demo_config(tmp_path / "buyer")
    store = Store.open(payment_store_path(buyer_cfg, payer_seed))
    buyer = build_buyer(buyer_cfg, payer_seed, store)  # pays on Dorado with CosmpySender
    buying = build_agent(buyer_cfg, None, seed=payer_seed, buyer=buyer)
    queues = [asyncio.create_task(agent._process_message_queue()) for agent in (seller, buying)]
    try:
        session, mark = await buyer.message(seller.address, "research: tides in the Bay of Fundy")
        replies = await _until(
            buyer,
            seller.address,
            session,
            mark,
            lambda seen: any(e.kind == "payment_request" for e in seen),
            60,
        )
        (asked,) = store.open_quotes(seller.address, session)
        shown = buyer.show(asked.id)
        purchase = await buyer.pay(
            shown.id,
            nonce=shown.nonce,
            expect_amount_base=shown.amount_base,
            expect_recipient=shown.recipient,
        )
        assert purchase.status in ("paid", "committed", "completed"), purchase
        replies += await _until(
            buyer,
            seller.address,
            session,
            replies[-1].id,
            lambda seen: any(e.kind == "end" for e in seen),
            180,
        )
        assert store.purchase(purchase.id).status == "completed"
        answer = " ".join(e.body for e in replies if e.kind == "text")
        assert "tides in the Bay of Fundy" in answer
    finally:
        for task in queues:
            task.cancel()
        await asyncio.gather(*queues, return_exceptions=True)
        for agent in (seller, buying):
            dispatcher.unregister(agent.address, agent)
        await buyer.aclose()
        await desk.aclose()
        store.close()


# -- Agentverse -----------------------------------------------------------------------------


def test_agentverse_search_answers_in_the_shape_the_bridge_reads():
    found = search_agents("research", limit=5, api_key=os.environ.get(AGENTVERSE_KEY_VAR))
    assert found, "Agentverse found no chat agents for 'research'"
    for agent in found:
        assert agent.address.startswith("agent1") and agent.name
        assert agent.interactions >= 0
