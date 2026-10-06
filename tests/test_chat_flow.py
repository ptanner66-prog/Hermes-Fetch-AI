"""A chat sale between two real uAgents in one process, the way ASI:One buys.

The buyer (hermes_fetch_ai.chat_demo) speaks the chat protocol and the
payment protocol's buyer role: it orders a service, pays the requested
amount on a fake ledger without a memo (as ASI:One's wallet does), commits
the payment, and waits for the answer. Messages travel through uAgents' own
dispatcher, so the protocol digests, roles, and handlers are the real ones.
"""

from hermes_fetch_ai import cli
from hermes_fetch_ai.chat_demo import chat_demo_config, run_chat_sale
from hermes_fetch_ai.fake_ledger import FakeLedger


async def test_an_asi_one_style_buyer_orders_pays_and_gets_the_answer(tmp_path):
    ledger = FakeLedger()
    received = await run_chat_sale(chat_demo_config(tmp_path), ledger, "research: tides")
    assert [type(message).__name__ for message in received] == [
        "ChatAcknowledgement",  # the order was acknowledged first
        "ChatMessage",  # the price
        "RequestPayment",  # ASI:One's payment card
        "CompletePayment",  # verified on the ledger
        "ChatMessage",  # the work has begun, so ASI:One waits for the answer
        "ChatMessage",  # the answer, ending the session
    ]
    assert received[2].metadata["fet_network"] == "stable-testnet"
    assert received[4].text().startswith("Payment confirmed. Working on")
    assert received[-1].text().startswith("tides")
    assert ledger.requests >= 2  # the bridge read the chain id and the transaction itself


def test_demo_chat_shows_the_buyers_side(capsys):
    assert cli.main(["demo", "chat"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("buyer says: research: tides in the Bay of Fundy\n")
    assert "payment card: pay 0.0500" in out and "on stable-testnet" in out
    assert "buyer pays, without a memo" in out
    assert "verified on the ledger" in out
    assert "seller says: tides in the Bay of Fundy" in out
