"""`serve` with buying set up, in its own process: the control channel's life cycle."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from hermes_fetch_ai import cli
from hermes_fetch_ai.wallet import BUYING_WALLET_INDEX, agent_address, wallet_address

from .test_serve_http_roundtrip import _request_graceful_stop, _wait_for_port

SEED = "serve-buying-test-" + "identity-material-not-a-real-seed"


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
        assert cli.main(["buyer", "purchases", "--config", str(config), "--json"]) == 0
        assert json.loads(capsys.readouterr().out) == []
        assert cli.main(["wallet", "--config", str(config)]) == 0
        assert f"buying wallet: {status['wallet']}" in capsys.readouterr().out
    finally:
        rc = _request_graceful_stop(proc)
    output = proc.stdout.read() if proc.stdout else ""
    assert rc == 0, f"serve did not shut down cleanly (rc={rc}):\n{output[-2000:]}"
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
