"""Hermes buys from another bridge: two real uAgents in one process.

The seller sells through chat, as for ASI:One users; the buyer is a bridge
with buying set up, driven the way Hermes' plugin drives it. Messages travel
through uAgents' own dispatcher, so protocol roles, routing, and sessions are
the real ones; only the ledger is simulated.
"""

from hermes_fetch_ai import cli
from hermes_fetch_ai.buy_demo import run_purchase
from hermes_fetch_ai.fake_ledger import FakeLedger


async def test_hermes_asks_pays_and_gets_the_answer(tmp_path):
    ledger = FakeLedger()
    replies, purchase = await run_purchase(tmp_path, ledger, "research: tides")
    assert [e.kind for e in replies] == [
        "text",  # the price, with this order's code
        "payment_request",  # nothing paid until the owner approves
        "payment_complete",  # the seller verified the payment on the ledger
        "text",  # the answer
        "end",
    ]
    assert len({e.session for e in replies}) == 1  # one conversation, one session
    assert replies[3].body.startswith("tides")
    assert purchase.status == "completed" and purchase.tx_hash
    tx = await ledger.get_tx(purchase.tx_hash)
    # Paid from the buying wallet with the seller's reference as the memo.
    assert tx is not None and tx.memo == purchase.reference
    assert tx.transfers[0].recipient == purchase.recipient
    assert tx.transfers[0].amount == purchase.amount_base


def test_demo_buy_shows_hermes_side(capsys):
    assert cli.main(["demo", "buy"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("hermes says: research: tides in the Bay of Fundy\n")
    assert "payment request: The agent asks for 0.0500" in out
    assert "owner approves: pay 0.0500" in out
    assert "seller says: tides in the Bay of Fundy" in out
    assert out.rstrip().endswith(": completed")
