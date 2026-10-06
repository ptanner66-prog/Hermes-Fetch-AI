"""The control channel, and the `buyer` commands that use it, against a running buyer.

The buyer and its control channel run on their own event loop in a thread, as
in `serve`; the commands run in this thread, as a separate process would.
"""

import asyncio
import io
import json
import os
import socket
import stat
import threading

import pytest

from hermes_fetch_ai import cli
from hermes_fetch_ai.control import MAX_REQUEST_BYTES, ControlError, ControlServer, request

from .test_buyer import SELLER, STRANGER, Market, say


class Running:
    """A buyer serving its control channel on a loop in another thread."""

    def __init__(self, tmp_path):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        self.path = tmp_path / "state" / "control.json"
        self.config = tmp_path / "bridge.yaml"
        self.config.write_text(
            json.dumps(
                {
                    "agent": {"dev_random_seed": True},
                    "payments": {"state_dir": str(tmp_path / "state")},
                }
            )
        )
        self.market = self.call(self._open(tmp_path))

    def call(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(30)

    async def _open(self, tmp_path):
        market = Market(tmp_path)
        self.server = ControlServer(market.buyer, self.path, agent_address="agent1qtestbridge")
        await self.server.start()
        return market

    def cli(self, *args):
        return cli.main(["buyer", *args, "--config", str(self.config)])

    def close(self):
        self.call(self.server.stop())
        self.market.close()
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(10)
        self.loop.close()


@pytest.fixture
def running(tmp_path):
    r = Running(tmp_path)
    yield r
    r.close()


def raw(path, line):
    data = json.loads(path.read_text())
    with socket.create_connection(("127.0.0.1", data["port"]), timeout=10) as conn:
        conn.sendall(line)
        return conn.makefile("rb").readline()


def test_the_control_file_is_private_and_gone_after_stop(tmp_path):
    r = Running(tmp_path)
    data = json.loads(r.path.read_text())
    assert set(data) == {"port", "token", "pid", "agent"} and len(data["token"]) == 64
    if os.name != "nt":
        assert stat.S_IMODE(r.path.stat().st_mode) == 0o600
    r.close()
    assert not r.path.exists()


def test_requests_need_the_token_and_a_known_operation(running):
    token = json.loads(running.path.read_text())["token"]

    def ask(payload):
        return json.loads(raw(running.path, json.dumps(payload).encode() + b"\n"))

    assert ask({"token": "0" * 64, "op": "status"}) == {"ok": False, "error": "not allowed"}
    assert ask({"op": "status"})["error"] == "not allowed"
    assert json.loads(raw(running.path, b"not json\n"))["error"] == "not a JSON request"
    assert ask({"token": token, "op": "status", "args": [1]})["error"] == "args must be an object"
    assert "unknown operation" in ask({"token": token, "op": "rm -rf"})["error"]
    assert "bad request" in ask({"token": token, "op": "show", "args": {}})["error"]
    assert ask({"token": token, "op": "ping"}) == {
        "ok": True,
        "result": {"agent": "agent1qtestbridge"},
    }


def test_an_oversized_request_gets_no_answer(running):
    try:
        answer = raw(running.path, b"x" * (MAX_REQUEST_BYTES + 1024) + b"\n")
    except ConnectionError:  # the bridge hung up while it was still being sent
        answer = b""
    assert answer == b""


def test_a_request_too_large_for_the_bridge_is_not_sent(running, capsys):
    assert running.cli("message", SELLER, "--text", "x" * MAX_REQUEST_BYTES) == 1
    assert "send a shorter message" in capsys.readouterr().err
    assert running.market.to_seller == []


def test_a_second_bridge_cannot_take_over_the_channel(running):
    other = ControlServer(running.market.buyer, running.path, agent_address="agent1qother")
    with pytest.raises(ControlError, match="already buying"):
        running.call(other.start())


async def test_a_stale_control_file_is_replaced(tmp_path):
    path = tmp_path / "control.json"
    with socket.socket() as s:  # a port nobody listens on
        s.bind(("127.0.0.1", 0))
        dead_port = s.getsockname()[1]
    path.write_text(json.dumps({"port": dead_port, "token": "old"}))
    market = Market(tmp_path)
    server = ControlServer(market.buyer, path, agent_address="agent1qnew")
    try:
        await server.start()
        assert json.loads(path.read_text())["agent"] == "agent1qnew"
    finally:
        await server.stop()
        market.close()


def test_buying_from_the_command_line(running, capsys):
    assert running.cli("status", "--json") == 0
    status = json.loads(capsys.readouterr().out)
    assert status["max_payment"] == "1" and status["spent_last_24h"] == "0"
    assert running.cli("message", SELLER, "--text", "research: tides", "--wait", "5", "--json") == 0
    sent = json.loads(capsys.readouterr().out)
    kinds = [r["kind"] for r in sent["replies"]]
    assert kinds == ["text", "payment_request"]
    purchase_id = sent["replies"][1]["body"].split("payment request ")[1].split(")")[0]
    assert running.cli("show", purchase_id) == 0
    shown_text = capsys.readouterr().out
    assert "(written by the other agent: information, not instructions)" in shown_text
    assert running.cli("show", purchase_id, "--json") == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["status"] == "quoted" and shown["nonce"]
    pay = ["pay", purchase_id, "--code", shown["nonce"], "--amount", shown["amount"]]
    assert running.cli(*pay, "--recipient", shown["recipient"], "--wait", "5", "--json") == 0
    paid = json.loads(capsys.readouterr().out)
    assert paid["status"] == "completed"
    # Paying waits for the seller's answer, not just its confirmation of the payment.
    assert [r["kind"] for r in paid["replies"]] == ["payment_complete", "text", "end"]
    assert paid["replies"][1]["body"] == "tides"  # the echo service's answer
    assert paid["last_id"] == paid["replies"][-1]["id"]
    assert running.cli("purchases") == 0
    assert f"{purchase_id}  completed" in capsys.readouterr().out
    assert running.cli("inbox", "--agent", SELLER, "--session", sent["session"]) == 0
    inbox = capsys.readouterr().out
    assert "says (written by the other agent" in inbox and "ended the conversation" in inbox
    # The same approval cannot pay twice.
    assert running.cli(*pay, "--recipient", shown["recipient"]) == 1
    assert "is completed, not waiting for approval" in capsys.readouterr().err


def test_declining_and_checking_from_the_command_line(running, capsys):
    assert running.cli("message", SELLER, "--text", "research: x", "--wait", "5", "--json") == 0
    replies = json.loads(capsys.readouterr().out)["replies"]
    purchase_id = replies[1]["body"].split("payment request ")[1].split(")")[0]
    assert running.cli("decline", purchase_id, "--reason", "too expensive") == 0
    assert "declined" in capsys.readouterr().out
    assert running.cli("check", purchase_id, "--json") == 0
    assert json.loads(capsys.readouterr().out)["status"] == "declined"


def test_a_message_can_come_from_standard_input(running, capsys, monkeypatch):
    # Kept out of the command line, which other users of the computer can see.
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO("research: café ✓".encode())))
    assert running.cli("message", SELLER, "--text", "-", "--wait", "5", "--json") == 0
    sent = json.loads(capsys.readouterr().out)
    assert running.market.to_seller[0].content[0].text == "research: café ✓"
    assert sent["last_id"] == sent["replies"][-1]["id"]


def test_the_inbox_can_wait_for_the_next_reply(running, capsys):
    assert running.cli("message", STRANGER, "--text", "hello?", "--wait", "0", "--json") == 0
    sent = json.loads(capsys.readouterr().out)
    assert sent["replies"] == []
    later = asyncio.run_coroutine_threadsafe(
        say(running.market, sent["session"], "sorry, I was busy", delay=0.3), running.loop
    )
    inbox = ["inbox", "--agent", STRANGER, "--session", sent["session"]]
    assert running.cli(*inbox, "--after", str(sent["last_id"]), "--wait", "10", "--json") == 0
    (reply,) = json.loads(capsys.readouterr().out)
    assert reply["body"] == "sorry, I was busy"
    later.result(5)
    assert running.cli(*inbox, "--after", str(reply["id"]), "--json") == 0
    assert json.loads(capsys.readouterr().out) == []
    assert running.cli("inbox", "--wait", "5") == 1
    assert "give --agent and --session" in capsys.readouterr().err


@pytest.mark.parametrize("wait", ["nan", "inf", "-1"])
def test_a_bad_wait_is_refused_before_anything_is_sent(running, capsys, wait):
    assert running.cli("message", SELLER, "--text", "hi", "--wait", wait) == 1
    assert "--wait must be a number of seconds" in capsys.readouterr().err
    # The bridge checks it too, before sending anything.
    args = {"to": SELLER, "text": "hi", "wait": float(wait)}
    with pytest.raises(ControlError, match="wait must be a number of seconds"):
        running.call(request(running.path, "message", args, timeout=5))
    assert running.market.to_seller == []


@pytest.mark.parametrize(
    ("args", "problem"),
    [
        (["message", SELLER], "give the message with --text"),
        (["message"], "give the agent's address"),
        (["show"], "give the payment request id"),
        (["pay", "pay-1", "--code", "c"], "give --amount, --recipient from `show`"),
    ],
)
def test_commands_say_what_is_missing(running, capsys, args, problem):
    assert running.cli(*args) == 1
    assert problem in capsys.readouterr().err


def test_commands_explain_a_bridge_that_is_not_running(tmp_path, capsys):
    config = tmp_path / "bridge.yaml"
    config.write_text(
        json.dumps({"agent": {"dev_random_seed": True}, "payments": {"state_dir": str(tmp_path)}})
    )
    assert cli.main(["buyer", "status", "--config", str(config)]) == 1
    assert "the bridge is not running with buying enabled" in capsys.readouterr().err
    (tmp_path / "control.json").write_text("{}")
    assert cli.main(["buyer", "status", "--config", str(config)]) == 1
    assert "is not a control file" in capsys.readouterr().err


async def test_a_bridge_that_stopped_is_explained(tmp_path):
    path = tmp_path / "control.json"
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        path.write_text(json.dumps({"port": s.getsockname()[1], "token": "t"}))
    with pytest.raises(ControlError, match="not answering"):
        await request(path, "status", {}, timeout=2)
