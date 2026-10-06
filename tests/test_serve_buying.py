"""`serve` with buying set up, in its own process: the control channel's life cycle."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import ClassVar

from hermes_fetch_ai import cli
from hermes_fetch_ai.money import parse_fet
from hermes_fetch_ai.store import Store
from hermes_fetch_ai.wallet import BUYING_WALLET_INDEX, agent_address, wallet_address

from .test_serve_http_roundtrip import _request_graceful_stop, _wait_for_port

SEED = "serve-buying-test-" + "identity-material-not-a-real-seed"
SELLER = "agent1qfuexnwkscrhfhx7tdchlz486mtzsl53grlnr3zpntxsyu6zhp2ckpemfdz"
PAYOUT = "fetch1hh09pm44murgmu7rpaxluwad3way3nxq0fl6fx"


def payment_left_mid_send(records: Path) -> str:
    """A payment the last run of the bridge stopped in the middle of sending."""
    now = int(time.time() * 1000)
    store = Store.open(records)
    try:
        store.add_quote(
            purchase_id="pay-0badf00d",
            peer=SELLER,
            session="6d0c1b0e-5e1d-4a52-9f0e-2a3c1d4e5f60",
            reference="order-1",
            recipient=PAYOUT,
            amount_base=parse_fet("0.1"),
            description="research",
            deadline_ms=now + 3_600_000,
            now_ms=now,
        )
        store.issue_nonce("pay-0badf00d", "c0de", now_ms=now)
        store.start_payment(
            "pay-0badf00d",
            nonce="c0de",
            expect_amount_base=parse_fet("0.1"),
            expect_recipient=PAYOUT,
            max_payment_base=parse_fet("0.5"),
            max_per_day_base=parse_fet("5"),
            max_per_seller_base=parse_fet("2"),
            allowed_sellers=[],
            now_ms=now,
        )
    finally:
        store.close()
    return "pay-0badf00d"


def test_serve_opens_the_control_channel_and_closes_it(
    tmp_path, unused_tcp_port, capsys, monkeypatch
):
    # The buyer commands load the same config, which names the seed it needs.
    monkeypatch.setenv("UAGENT_SEED", SEED)
    state = tmp_path / "state"
    config = tmp_path / "buyer.yaml"
    config.write_text(
        "version: 1\n"
        "agent:\n"
        "  name: bridge_buying_smoke\n"
        f"  port: {unused_tcp_port}\n"
        f"  endpoint: http://127.0.0.1:{unused_tcp_port}/submit\n"
        "  publish_manifest: false\n"
        "hermes_mcp:\n"
        "  mode: fake\n"
        "payments:\n"
        "  ledger_url: http://127.0.0.1:9\n"
        f"  state_dir: {json.dumps(str(state))}\n"
        "buying:\n"
        "  enabled: true\n"
        '  max_payment: "0.5"\n'
        "logging:\n"
        f"  audit_path: {json.dumps(str(tmp_path / 'audit.jsonl'))}\n",
        encoding="utf-8",
    )
    stuck = payment_left_mid_send(state / agent_address(SEED) / "payments.sqlite3")
    env = dict(os.environ)
    env["UAGENT_" + "SEED"] = SEED
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    proc = subprocess.Popen(
        [sys.executable, "-m", "hermes_fetch_ai.cli", "serve", "--config", str(config)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=creationflags,
    )
    control = state / "control.json"
    try:
        _wait_for_port(unused_tcp_port)
        deadline = time.monotonic() + 20
        while not control.exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        assert control.exists()
        assert cli.main(["buyer", "status", "--config", str(config), "--json"]) == 0
        status = json.loads(capsys.readouterr().out)
        assert status["agent"] == agent_address(SEED)
        assert status["wallet"] == wallet_address(SEED, BUYING_WALLET_INDEX)
        assert status["max_payment"] == "0.5"
        # A payment the last run stopped in the middle of sending waits for `check`.
        assert cli.main(["buyer", "purchases", "--config", str(config), "--json"]) == 0
        (purchase,) = json.loads(capsys.readouterr().out)
        assert (purchase["id"], purchase["status"]) == (stuck, "needs_review")
        assert "stopped while sending" in purchase["note"]
        assert cli.main(["wallet", "--config", str(config)]) == 0
        assert f"buying wallet: {status['wallet']}" in capsys.readouterr().out
    finally:
        rc = _request_graceful_stop(proc)
    output = proc.stdout.read() if proc.stdout else ""
    assert rc == 0, f"serve did not shut down cleanly (rc={rc}):\n{output[-2000:]}"
    assert f"payment {stuck} was being sent when the bridge stopped" in output
    assert not control.exists()
    assert SEED not in output
    # Buying keeps its records next to the selling ones.
    assert (state / agent_address(SEED) / "payments.sqlite3").exists()


def test_wallet_without_buying_shows_no_buying_wallet(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("UAGENT_SEED", SEED)
    config = tmp_path / "c.yaml"
    config.write_text(json.dumps({"payments": {"state_dir": str(Path(tmp_path))}}))
    assert cli.main(["wallet", "--config", str(config)]) == 0
    assert "buying wallet" not in capsys.readouterr().out


class Faucet:
    asked: ClassVar[list[tuple[str, str]]] = []
    fail = False

    def __init__(self, network):
        self.network = network

    def get_wealth(self, address):
        if Faucet.fail:
            raise RuntimeError("faucet is dry")
        Faucet.asked.append((self.network.chain_id, address))


def test_wallet_fund_fills_the_buying_wallet_from_the_faucet(tmp_path, monkeypatch, capsys):
    import cosmpy.aerial.faucet

    monkeypatch.setenv("UAGENT_SEED", SEED)
    monkeypatch.setattr(cosmpy.aerial.faucet, "FaucetApi", Faucet)
    Faucet.asked, Faucet.fail = [], False
    config = tmp_path / "c.yaml"
    config.write_text(json.dumps({"buying": {"enabled": True}}))
    assert cli.main(["wallet", "--config", str(config), "--fund"]) == 0
    assert Faucet.asked == [("dorado-1", wallet_address(SEED, BUYING_WALLET_INDEX))]
    assert "can take a minute to arrive" in capsys.readouterr().out
    Faucet.fail = True
    assert cli.main(["wallet", "--config", str(config), "--fund"]) == 1
    assert "the faucet did not pay (faucet is dry)" in capsys.readouterr().err
    config.write_text("{}")
    assert cli.main(["wallet", "--config", str(config), "--fund"]) == 1
    assert "set buying.enabled: true" in capsys.readouterr().err
