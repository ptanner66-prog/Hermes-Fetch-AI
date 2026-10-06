"""Paid services through the bridge's MCP handlers, as a remote agent sees them."""

import json
import time

import pytest
from uagents_adapter.mcp.protocol import CallTool

from hermes_fetch_ai.audit import AuditWriter
from hermes_fetch_ai.config import BridgeConfig
from hermes_fetch_ai.direct_protocol import handle_call_tool, handle_list_tools, replay_args
from hermes_fetch_ai.fake_ledger import FakeLedger
from hermes_fetch_ai.policy import PolicyState
from hermes_fetch_ai.quotes import quote_key
from hermes_fetch_ai.result_normalizer import NormalizedToolResult
from hermes_fetch_ai.seller import Seller, parse_payment_terms
from hermes_fetch_ai.services import ServiceDesk
from hermes_fetch_ai.store import Store

PAYOUT = "fetch1hh09pm44murgmu7rpaxluwad3way3nxq0fl6fx"
BUYER = "agent1qbuyerbuyerbuyerbuyerbuyerbuyerbuyerbuyerbuyerbuyerbuyer"
KEY = quote_key("only for these tests, at least thirty-two characters")


class Shim:
    def __init__(self):
        self.calls = 0

    async def list_tools(self):
        return [{"name": "echo", "inputSchema": {"type": "object"}}]

    async def call_tool(self, name, args):
        self.calls += 1
        return NormalizedToolResult("tool ran", False, False, 8)


def config(**policy):
    return BridgeConfig.model_validate(
        {
            "agent": {"dev_random_seed": True},
            "policy": policy,
            "payments": {"enabled": True, "payout_address": PAYOUT},
            "services": {
                "research": {
                    "title": "Research a topic",
                    "description": "Finds sources.",
                    "price": "0.05",
                    "runner": {"type": "echo"},
                }
            },
        }
    )


class Bridge:
    """One bridge's handlers, store, and ledger; ``restart()`` keeps the store."""

    def __init__(self, tmp_path, **policy):
        self.cfg = config(**policy)
        self.ledger = FakeLedger()
        self.store_path = tmp_path / "payments.sqlite3"
        self.audit_path = tmp_path / "audit.jsonl"
        self.audit = AuditWriter(self.audit_path)
        self.shim = Shim()
        self.restart()

    def restart(self):
        self.state = PolicyState()
        seller = Seller(
            payments=self.cfg.payments,
            store=Store.open(self.store_path),
            key=KEY,
            payout=PAYOUT,
            ledger_factory=lambda: self.ledger,
        )
        self.desk = ServiceDesk(self.cfg, seller)

    async def call(self, args, tool="service.research", sender=BUYER):
        return await handle_call_tool(
            sender,
            CallTool(tool=tool, args=args),
            self.shim,
            self.cfg,
            self.audit,
            state=self.state,
            desk=self.desk,
        )

    def pay(self, terms, **overrides):
        return self.ledger.pay(
            payer="fetch1buyerwallet",
            recipient=terms["recipient"],
            amount_base=int(terms["amount_base"]),
            memo=terms["memo"],
            **overrides,
        )

    def audit_events(self):
        return [
            json.loads(line) for line in self.audit_path.read_text(encoding="utf-8").splitlines()
        ]

    def close(self):
        self.desk.seller.store.close()


@pytest.fixture
def bridge(tmp_path):
    b = Bridge(tmp_path)
    yield b
    b.close()


async def test_list_tools_includes_services_for_everyone(bridge):
    resp = await handle_list_tools(
        BUYER, bridge.shim, bridge.cfg, bridge.audit, state=bridge.state, desk=bridge.desk
    )
    names = [tool["name"] for tool in resp.tools]
    # "echo" is not public, so only the service is visible.
    assert names == ["service.research"]


async def test_payment_required_does_not_use_up_the_request_id(bridge):
    args = replay_args({"request": "topic"}, "req-paid-00001")
    first = await bridge.call(args)
    terms = parse_payment_terms(first.error)
    assert terms["amount"] == "0.05" and first.result is None
    tx_hash = bridge.pay(terms)
    paid_args = replay_args(
        {"request": "topic"},
        "req-paid-00001",  # the same request ID still works after the quote
        payment={"reference": terms["reference"], "tx_hash": tx_hash},
    )
    paid = await bridge.call(paid_args)
    assert (paid.result, paid.error) == ("topic", None)
    # A copy of the exact paid message is refused; the buyer's own new message
    # with the same payment gets the same answer, and the service does not run again.
    replayed = await bridge.call(paid_args)
    assert replayed.error == "replay detected"
    proof = {"reference": terms["reference"], "tx_hash": tx_hash}
    again = await bridge.call(replay_args({"request": "topic"}, payment=proof))
    assert (again.result, again.error) == ("topic", None)


async def test_paid_call_runs_once_even_across_restarts(bridge):
    terms = parse_payment_terms((await bridge.call(replay_args({"request": "topic"}))).error)
    proof = {"reference": terms["reference"], "tx_hash": bridge.pay(terms)}
    assert (await bridge.call(replay_args({"request": "topic"}, payment=proof))).result == "topic"
    bridge.close()
    bridge.restart()  # fresh replay cache and no kept answers; same payment records
    again = await bridge.call(replay_args({"request": "topic"}, payment=proof))
    assert "already used for a completed request" in again.error


async def test_audit_records_payments_in_short_form_only(bridge):
    terms = parse_payment_terms((await bridge.call(replay_args({"request": "topic"}))).error)
    tx_hash = bridge.pay(terms)
    proof = {"reference": terms["reference"], "tx_hash": tx_hash}
    await bridge.call(replay_args({"request": "topic"}, payment=proof))
    required, verified = bridge.audit_events()
    assert (required["decision"], required["payment"]) == ("payment", "required")
    assert (verified["decision"], verified["payment"]) == ("allowed", "verified")
    assert verified["amount_base"] == "50000000000000000"
    log = bridge.audit_path.read_text(encoding="utf-8")
    assert tx_hash not in log and terms["reference"] not in log and "fetch1buyerwallet" not in log
    assert verified["tx_short"] == f"{tx_hash[:8]}…{tx_hash[-4:]}"


async def test_denylist_still_wins_over_services(tmp_path):
    bridge = Bridge(tmp_path, denied_tools=["service.research"])
    try:
        resp = await bridge.call(replay_args({"request": "topic"}))
        assert resp.error == "tool denied"
        listed = await handle_list_tools(
            BUYER, bridge.shim, bridge.cfg, bridge.audit, state=bridge.state, desk=bridge.desk
        )
        assert listed.tools == []
    finally:
        bridge.close()


@pytest.mark.parametrize(
    "payment",
    [
        "not-an-object",
        {"reference": "r"},
        {"reference": "r", "tx_hash": "t", "extra": "x"},
        {"reference": "", "tx_hash": "t"},
        {"reference": "r" * 200, "tx_hash": "t"},
        {"reference": 1, "tx_hash": "t"},
    ],
)
async def test_malformed_payment_proof_is_refused(bridge, payment):
    args = {
        "request": "topic",
        "_hermes_fetch_ai": {
            "request_id": "req-proof-00001",
            "issued_at_ms": int(time.time() * 1000),
            "payment": payment,
        },
    }
    assert (await bridge.call(args)).error == "invalid payment proof"


async def test_services_still_need_replay_metadata(bridge):
    assert (await bridge.call({"request": "topic"})).error == "missing replay metadata"


async def test_payment_on_a_free_tool_is_ignored(tmp_path):
    bridge = Bridge(tmp_path, public_tools=["echo"])
    try:
        args = replay_args({}, payment={"reference": "r", "tx_hash": "t"})
        resp = await bridge.call(args, tool="echo")
        assert resp.result == "tool ran" and bridge.shim.calls == 1
    finally:
        bridge.close()


async def test_underpayment_is_refused_and_recorded_nowhere(bridge):
    terms = parse_payment_terms((await bridge.call(replay_args({"request": "topic"}))).error)
    tx_hash = bridge.ledger.pay(
        payer="fetch1buyerwallet",
        recipient=terms["recipient"],
        amount_base=int(terms["amount_base"]) - 1,
        memo=terms["memo"],
    )
    resp = await bridge.call(
        replay_args(
            {"request": "topic"}, payment={"reference": terms["reference"], "tx_hash": tx_hash}
        )
    )
    assert resp.error.startswith("payment invalid: underpaid")
    assert not bridge.desk.seller.store.tx_used(tx_hash)
    assert bridge.audit_events()[-1]["payment"] == "invalid"
