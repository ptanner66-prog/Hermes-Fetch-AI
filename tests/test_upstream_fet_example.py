"""The checks proposed to Fetch.ai's fet-example (upstream/fetch-examples/...) do what they say.

The patch adds fet-example/verify.py; this takes that file from the patch itself,
so the test and the proposal cannot drift apart.
"""

import importlib.util
from pathlib import Path

import pytest
from cosmpy.protos.cosmos.bank.v1beta1.tx_pb2 import MsgSend
from cosmpy.protos.cosmos.base.v1beta1.coin_pb2 import Coin
from cosmpy.protos.cosmos.tx.v1beta1.tx_pb2 import Tx, TxBody

PATCH = Path("upstream/fetch-examples/fet-example-payment-checks/fet-example-payment-checks.patch")
SELLER = "fetch1hh09pm44murgmu7rpaxluwad3way3nxq0fl6fx"
BUYER = "fetch1zy4vnxqyt0mqe2j6pzmkf3cxmh83vj7vp9cuaw"


def new_file(patch: str, name: str) -> str:
    """The text of a file the patch adds."""
    lines = patch.splitlines()
    start = lines.index(f"+++ b/{name}")
    body = []
    for line in lines[start + 1 :]:
        if line.startswith("--- "):
            break
        if line.startswith("+"):
            body.append(line[1:])
        elif line.startswith(("@@", "\\")):
            continue
        else:
            raise AssertionError(f"{name} is not a new file in the patch: {line!r}")
    return "\n".join(body) + "\n"


@pytest.fixture(scope="module")
def verify(tmp_path_factory):
    path = tmp_path_factory.mktemp("fet-example") / "verify.py"
    path.write_text(new_file(PATCH.read_text(encoding="utf-8"), "fet-example/verify.py"))
    spec = importlib.util.spec_from_file_location("fet_example_verify", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MSG_SEND = "/cosmos.bank.v1beta1.MsgSend"


def send(sender, recipient, amount, denom="atestfet"):
    coins = [Coin(denom=denom, amount=str(amount))]
    message = MsgSend(from_address=sender, to_address=recipient, amount=coins)
    return MSG_SEND, message.SerializeToString()


def tx(*messages):
    body = TxBody()
    for type_url, value in messages:
        packed = body.messages.add()
        packed.type_url, packed.value = type_url, value
    return Tx(body=body)


def test_fet_amounts_convert_exactly(verify):
    assert verify.fet_to_base("0.1") == 10**17
    assert verify.fet_to_base("1.1") == 11 * 10**17  # int(float("1.1") * 10**18) is 128 too many
    assert verify.fet_to_base("0.000000000000000001") == 1
    for bad in ("0", "-1", "nan", "inf", "abc", "0.0000000000000000001"):
        with pytest.raises(ValueError):
            verify.fet_to_base(bad)


def test_transaction_hashes_are_normalized(verify):
    assert verify.normalize_tx_hash("0x" + "ab" * 32) == "AB" * 32
    assert verify.normalize_tx_hash(" " + "CD" * 32 + "\n") == "CD" * 32
    for bad in ("ab" * 31, "zz" * 32, ""):
        with pytest.raises(ValueError):
            verify.normalize_tx_hash(bad)


def test_only_the_buyers_sends_to_the_seller_in_the_denomination_count(verify):
    split = tx(send(BUYER, SELLER, 6 * 10**16), send(BUYER, SELLER, 4 * 10**16))
    assert verify.paid_to(split, SELLER, BUYER, "atestfet") == 10**17
    others = tx(
        send("fetch1someoneelse", SELLER, 10**17),
        send(BUYER, "fetch1elsewhere", 10**17),
        send(BUYER, SELLER, 10**17, "afet"),
        ("/cosmos.staking.v1beta1.MsgDelegate", b""),
    )
    assert verify.paid_to(others, SELLER, BUYER, "atestfet") == 0
