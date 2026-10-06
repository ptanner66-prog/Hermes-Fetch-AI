"""Checks fet-example's CommitPayment handler against a stand-in ledger.

Run it on a checkout of fetchai/innovation-lab-examples, before and after the patch:

    python check_payment.py path/to/innovation-lab-examples/fet-example

It needs uagents, uagents-core, and cosmpy, which the example already uses, and
it touches no network: the ledger is a stand-in built from cosmpy's own types,
and the example's `shared` module (which calls the ASI:One API) is replaced.
"""

import asyncio
import os
import sys
import types
from typing import ClassVar

SELLER = "fetch1hh09pm44murgmu7rpaxluwad3way3nxq0fl6fx"
BUYER = "fetch1zy4vnxqyt0mqe2j6pzmkf3cxmh83vj7vp9cuaw"


def main(example: str) -> int:
    sys.path.insert(0, example)
    sys.modules["shared"] = types.SimpleNamespace(create_text_chat=lambda *a, **k: None)
    import payment
    from cosmpy.aerial import client
    from cosmpy.aerial.tx_helpers import TxResponse as Summary
    from cosmpy.protos.cosmos.bank.v1beta1.tx_pb2 import MsgSend
    from cosmpy.protos.cosmos.base.abci.v1beta1.abci_pb2 import TxResponse
    from cosmpy.protos.cosmos.base.v1beta1.coin_pb2 import Coin
    from cosmpy.protos.cosmos.tx.v1beta1.service_pb2 import GetTxResponse
    from cosmpy.protos.cosmos.tx.v1beta1.tx_pb2 import Tx, TxBody
    from google.protobuf.any_pb2 import Any as AnyProto
    from uagents_core.contrib.protocols.payment import CommitPayment, Funds

    def send(sender, recipient, amount, denom="atestfet"):
        coins = [Coin(denom=denom, amount=str(amount))]
        message = MsgSend(from_address=sender, to_address=recipient, amount=coins)
        return AnyProto(type_url="/cosmos.bank.v1beta1.MsgSend", value=message.SerializeToString())

    class Ledger:
        messages: ClassVar[list] = []

        def __init__(self, network):
            self.txs = self

        def query_tx(self, tx_hash):
            # cosmpy's summary keeps one entry per event type: a later transfer replaces an earlier.
            events = {}
            for message in Ledger.messages:
                sent = MsgSend.FromString(message.value)
                for coin in sent.amount:
                    events["transfer"] = {
                        "recipient": sent.to_address,
                        "sender": sent.from_address,
                        "amount": f"{coin.amount}{coin.denom}",
                    }
            return Summary(tx_hash, 1, 0, 0, 0, "", [], events, None)

        def GetTx(self, request):
            body = TxBody(messages=Ledger.messages)
            return GetTxResponse(tx=Tx(body=body), tx_response=TxResponse(code=0))

    class Wallet:
        def address(self):
            return SELLER

    class Storage(dict):
        def set(self, key, value):
            self[key] = value

        def remove(self, key):
            self.pop(key, None)

    class Ctx:
        def __init__(self):
            self.storage, self.sent, self.session = Storage(), [], "session-1"
            quiet = types.SimpleNamespace(info=print, error=print, warning=print)
            self.logger = quiet if os.environ.get("VERBOSE") else _silent()

        async def send(self, to, message):
            self.sent.append(type(message).__name__)

    delivered = []

    async def deliver(ctx, sender):
        delivered.append(sender)

    client.LedgerClient = Ledger
    payment.set_agent_wallet(Wallet())
    payment.generate_response_after_payment = deliver

    def commit(claimed, tx_hash):
        funds = Funds(amount=claimed, currency="FET", payment_method="fet_direct")
        metadata = {"buyer_fet_wallet": BUYER}
        return CommitPayment(
            funds=funds, recipient=SELLER, transaction_id=tx_hash, metadata=metadata
        )

    def run(ctx, price, messages, claimed, tx_hash="0x" + "ab" * 32):
        os.environ["FIXED_FET_AMOUNT"] = price
        Ledger.messages = messages
        before = len(delivered)
        asyncio.run(payment.handle_commit_payment(ctx, "agent1buyer", commit(claimed, tx_hash)))
        return ctx.sent[-1] == "CompletePayment" and len(delivered) == before + 1

    price = 10**17  # 0.1 FET
    ctx = Ctx()
    results = {"pays the price": run(ctx, "0.1", [send(BUYER, SELLER, price)], "0.1")}
    results["the same transaction again is refused"] = not run(
        ctx, "0.1", [send(BUYER, SELLER, price)], "0.1"
    )
    refused = {
        "a buyer who claims 0 and pays 1 atestfet": ([send(BUYER, SELLER, 1)], "0"),
        "an underpayment of 1 atestfet": ([send(BUYER, SELLER, price - 1)], "0.1"),
        "the wrong denomination": ([send(BUYER, SELLER, price, "afet")], "0.1"),
        "someone else's transfer": ([send("fetch1someoneelse", SELLER, price)], "0.1"),
    }
    for name, (messages, claimed) in refused.items():
        results[f"refused: {name}"] = not run(Ctx(), "0.1", messages, claimed)
    split = [send(BUYER, SELLER, 6 * 10**16), send(BUYER, SELLER, 4 * 10**16)]
    results["two transfers that add up count"] = run(Ctx(), "0.1", split, "0.1")
    exact = [send(BUYER, SELLER, 11 * 10**17)]
    results["exactly 1.1 FET counts"] = run(Ctx(), "1.1", exact, "1.1", "0x" + "cd" * 32)
    for name, ok in results.items():
        print(("PASS " if ok else "FAIL ") + name)
    return 0 if all(results.values()) else 1


def _silent():
    return types.SimpleNamespace(info=_quiet, error=_quiet, warning=_quiet)


def _quiet(*args, **kwargs):
    pass


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
