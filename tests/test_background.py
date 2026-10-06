"""Running the bridge in the background (`start`, `stop`, `restart`, `logs`) and `status`."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from hermes_fetch_ai import background, cli
from hermes_fetch_ai.background import (
    RUN_FILE,
    STOP_FILE,
    AlreadyRunning,
    claim,
    pid_alive,
    read_running,
    release,
)
from hermes_fetch_ai.config import BridgeConfig
from hermes_fetch_ai.ledger import LcdLedgerReader, LedgerUnavailable
from hermes_fetch_ai.money import parse_fet
from hermes_fetch_ai.status import report
from hermes_fetch_ai.store import Store
from hermes_fetch_ai.uagent_app import payment_store_path
from hermes_fetch_ai.wallet import BUYING_WALLET_INDEX, wallet_address

SEED = "background-test-" + "identity-material-not-a-real-seed"
SELLER = "agent1qfuexnwkscrhfhx7tdchlz486mtzsl53grlnr3zpntxsyu6zhp2ckpemfdz"
PAYOUT = "fetch1hh09pm44murgmu7rpaxluwad3way3nxq0fl6fx"


@pytest.fixture
def seed(monkeypatch):
    monkeypatch.setenv("UAGENT_SEED", SEED)
    return SEED


def write_config(tmp_path: Path, port: int, **extra) -> Path:
    path = tmp_path / "bridge.yaml"
    config = {
        "agent": {
            "name": "background_test",
            "port": port,
            "endpoint": f"http://127.0.0.1:{port}/submit",
        },
        "payments": {"ledger_url": "http://127.0.0.1:9", "state_dir": str(tmp_path / "state")},
        **extra,
    }
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def sleeper(*extra: str, ignore_term: bool = False) -> subprocess.Popen[bytes]:
    """A process whose command line names the bridge, as `serve`'s does."""
    code = "import signal, time\n"
    if ignore_term:
        code += "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
    code += "time.sleep(60)\n"
    return subprocess.Popen([sys.executable, "-c", code, "hermes_fetch_ai", *extra])


# -- one bridge per records folder -----------------------------------------------------


def test_serve_claims_the_records_folder_and_lets_go(tmp_path, monkeypatch):
    monkeypatch.setattr(background, "is_bridge", lambda pid: pid_alive(pid))
    state = tmp_path / "state"
    info = claim(state, tmp_path / "bridge.yaml")
    assert info.pid == os.getpid()
    assert read_running(state) == info
    (state / STOP_FILE).write_text("stop")
    release(state)
    assert read_running(state) is None
    assert not (state / STOP_FILE).exists()


def test_a_second_bridge_with_the_same_records_is_refused(tmp_path, monkeypatch):
    state = tmp_path / "state"
    other = sleeper()
    try:
        state.mkdir()
        run = {"pid": other.pid, "started": time.time(), "config": "x", "log": None}
        (state / RUN_FILE).write_text(json.dumps(run))
        with pytest.raises(AlreadyRunning, match="already running with these records"):
            claim(state, tmp_path / "bridge.yaml")
    finally:
        other.kill()
        other.wait()
    # Once it is gone, its leftover file does not count.
    assert read_running(state) is None
    assert not (state / RUN_FILE).exists()
    monkeypatch.setattr(background, "is_bridge", lambda pid: pid_alive(pid))
    assert claim(state, tmp_path / "bridge.yaml").pid == os.getpid()
    release(state)


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no command lines to read here")
def test_a_reused_process_id_is_not_mistaken_for_the_bridge(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    stranger = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        run = {"pid": stranger.pid, "started": 0, "config": "x"}
        (state / RUN_FILE).write_text(json.dumps(run))
        assert read_running(state) is None
    finally:
        stranger.kill()
        stranger.wait()


def test_process_checks():
    assert pid_alive(os.getpid())
    assert not pid_alive(0) and not pid_alive(-5)
    done = subprocess.Popen([sys.executable, "-c", "pass"])
    done.wait()
    assert not pid_alive(done.pid)


# -- start, stop, restart, logs ----------------------------------------------------------


def test_start_status_logs_and_stop(tmp_path, seed, unused_tcp_port, capsys):
    config = write_config(tmp_path, unused_tcp_port, buying={"enabled": True})
    args = ["--config", str(config)]
    try:
        assert cli.main(["start", *args]) == 0
        out = capsys.readouterr().out
        assert "Your agent is running" in out and "serve.log" in out
        assert cli.main(["start", *args]) == 0
        assert "already running" in capsys.readouterr().out
        assert cli.main(["serve", *args]) == 1
        assert "already running with these records" in capsys.readouterr().err
        assert cli.main(["status", "--offline", *args]) == 0
        out = capsys.readouterr().out
        assert "Your agent is running: for" in out
        assert "Reached:        from this computer only" in out
        assert "Buying:         on, up to 1 FET a payment and 5 a day" in out
        assert cli.main(["logs", "--lines", "50", *args]) == 0
        assert "Starting agent with address" in capsys.readouterr().out
    finally:
        stopped = cli.main(["stop", *args])
    assert stopped == 0
    assert "Your agent stopped." in capsys.readouterr().out
    state = tmp_path / "state"
    assert not (state / RUN_FILE).exists()
    assert cli.main(["stop", *args]) == 0
    assert "not running" in capsys.readouterr().out
    assert cli.main(["status", "--offline", *args]) == 3
    if os.name != "nt":
        assert oct((state / "serve.log").stat().st_mode & 0o777) == "0o600"
    assert SEED not in (state / "serve.log").read_text()


def test_restart_stops_and_starts_again(tmp_path, seed, unused_tcp_port, capsys):
    config = write_config(tmp_path, unused_tcp_port)
    args = ["--config", str(config)]
    try:
        assert cli.main(["start", *args]) == 0
        first = read_running(tmp_path / "state")
        assert first is not None
        assert cli.main(["restart", *args]) == 0
        second = read_running(tmp_path / "state")
        assert second is not None and second.pid != first.pid
    finally:
        assert cli.main(["stop", *args]) == 0
    assert "Your agent stopped." in capsys.readouterr().out


def test_a_bridge_that_cannot_start_shows_why(tmp_path, seed, unused_tcp_port, capsys):
    config = write_config(tmp_path, unused_tcp_port)
    with socket.socket() as busy:  # something else holds the agent's port
        busy.bind(("0.0.0.0", unused_tcp_port))
        busy.listen()
        assert cli.main(["start", "--config", str(config)]) == 1
    out = capsys.readouterr().out
    assert "Your agent could not start. The end of its log:" in out
    assert read_running(tmp_path / "state") is None


@pytest.mark.skipif(sys.platform == "win32", reason="stop uses a stop file on Windows")
def test_a_bridge_that_will_not_stop_is_stopped(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    stubborn = sleeper(ignore_term=True)
    try:
        time.sleep(0.3)  # let it ignore SIGTERM before being asked
        run = {"pid": stubborn.pid, "started": time.time(), "config": "x"}
        (state / RUN_FILE).write_text(json.dumps(run))
        lines: list[str] = []
        assert background.stop(state, wait=1, out=lines.append) == 1
        assert "did not stop within 1 seconds" in lines[0]
        assert stubborn.wait(10) != 0
    finally:
        stubborn.kill()
        stubborn.wait()


def test_logs_without_a_log_and_a_big_log_is_set_aside(tmp_path, seed, monkeypatch, capsys):
    config = write_config(tmp_path, 9)
    assert cli.main(["logs", "--config", str(config)]) == 1
    assert "No log yet" in capsys.readouterr().out
    state = tmp_path / "state"
    state.mkdir()
    log = state / "serve.log"
    log.write_text("old line\n" * 10)
    monkeypatch.setattr(background, "MAX_LOG_BYTES", 20)
    background._rotate(log)
    assert not log.exists() and (state / "serve.log.1").exists()
    log.write_text("".join(f"line {n}\n" for n in range(100)))
    assert cli.main(["logs", "--lines", "3", "--config", str(config)]) == 0
    assert capsys.readouterr().out.splitlines() == ["line 97", "line 98", "line 99"]
    assert background.tail(tmp_path / "missing", 3) == []


def test_follow_prints_new_lines_as_they_come(tmp_path):
    log = tmp_path / "serve.log"
    log.write_text("before\n")
    seen: list[str] = []

    def out(line: str) -> None:
        seen.append(line)
        if len(seen) == 2:
            raise KeyboardInterrupt

    def write() -> None:
        time.sleep(0.2)
        with log.open("a") as f:
            f.write("one\ntwo\n")

    threading.Thread(target=write).start()
    with pytest.raises(KeyboardInterrupt):
        background.follow(log, out, poll=0.02)
    assert seen == ["one", "two"]


def test_serve_stops_when_the_stop_file_appears(tmp_path, seed, unused_tcp_port):
    config = write_config(tmp_path, unused_tcp_port)
    state = tmp_path / "state"
    proc = subprocess.Popen(
        [sys.executable, "-m", "hermes_fetch_ai.cli", "serve", "--config", str(config)],
        env=dict(os.environ),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.monotonic() + 30
        while read_running(state) is None and time.monotonic() < deadline:
            time.sleep(0.1)
        assert read_running(state) is not None
        (state / STOP_FILE).write_text("stop")
        assert proc.wait(30) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    assert not (state / RUN_FILE).exists() and not (state / STOP_FILE).exists()


# -- status ------------------------------------------------------------------------------


class Chain:
    def __init__(self, balances, newest_ms, *, fail=False):
        self.balances = balances
        self.newest_ms = newest_ms
        self.fail = fail

    async def balance(self, address, denom):
        if self.fail:
            raise LedgerUnavailable("the ledger did not answer (ConnectTimeout)")
        return self.balances[address]

    async def latest_block_ms(self):
        return self.newest_ms

    async def aclose(self):
        return None


def selling_config(tmp_path, **buying):
    return BridgeConfig.model_validate(
        {
            "agent": {"name": "status_test", "mode": "mailbox", "handle": "hermes-desk"},
            "payments": {"enabled": True, "state_dir": str(tmp_path / "state")},
            "chat": {"enable_chat": True},
            "services": {
                "research": {
                    "title": "Research",
                    "description": "Finds sources.",
                    "price": "0.05",
                    "runner": {"type": "echo"},
                }
            },
            "buying": {"enabled": True, **buying},
        }
    )


def test_status_in_plain_words(tmp_path, seed):
    cfg = selling_config(tmp_path)
    now = 1_800_000_000.0
    store = Store.open(payment_store_path(cfg, SEED))
    try:
        for n, status in enumerate(("done", "failed")):
            store._conn.execute(
                "INSERT INTO credits VALUES (?, 'chat', ?, 'research', 'd', ?, ?, ?, ?, 1, ?, ?, ?)",
                (
                    f"ref-{n}",
                    SELLER,
                    str(parse_fet("0.05")),
                    f"{n}" * 64,
                    "fetch1payer",
                    status,
                    int(now * 1000) - 1000,
                    int(now * 1000) - 1000,
                    int(now * 1000),
                ),
            )
        store.set_paused(True)
        store.add_quote(
            purchase_id="pay-1a2b3c4d",
            peer=SELLER,
            session="s",
            reference=None,
            recipient=PAYOUT,
            amount_base=parse_fet("0.1"),
            description="research",
            deadline_ms=int(now * 1000) + 60_000,
            now_ms=int(now * 1000),
        )
    finally:
        store.close()
    income, buying = wallet_address(SEED), wallet_address(SEED, BUYING_WALLET_INDEX)
    lines: list[str] = []
    code = report(
        cfg,
        out=lines.append,
        chain=lambda: Chain({income: parse_fet("1.25"), buying: 0}, int(now * 1000) - 4000),
        now=lambda: now,
    )
    text = "\n".join(lines)
    assert code == 3 and lines[0].startswith("Your agent is not running.")
    assert (
        "Reached:        through its Agentverse mailbox, from anywhere; ASI:One users can "
        "write to @hermes-desk" in text
    )
    assert (
        "Selling:        research 0.05 FET  (paused: hermes fetchai-bridge seller resume)" in text
    )
    assert "2 paid request(s) in the last day, 0.1 test FET" in text
    assert "1 paid request(s) failed after every retry" in text
    assert "1 payment request(s) waiting for your answer" in text
    assert f"Income wallet:  {income}  1.25 test FET" in text
    assert "empty; get free test FET: hermes fetchai-bridge wallet --fund" in text
    assert "Testnet:        working (newest block 4 seconds ago)" in text


def test_status_when_the_testnet_stalls_or_does_not_answer(tmp_path, seed):
    cfg = selling_config(tmp_path)
    now = 1_800_000_000.0
    income, buying = wallet_address(SEED), wallet_address(SEED, BUYING_WALLET_INDEX)
    balances = {income: 0, buying: parse_fet("2")}
    lines: list[str] = []
    report(
        cfg,
        out=lines.append,
        chain=lambda: Chain(balances, int(now * 1000) - 600_000),
        now=lambda: now,
    )
    assert any("the chain may have stopped" in line for line in lines)
    assert any("no sales yet" in line for line in lines)
    lines.clear()
    report(cfg, out=lines.append, chain=lambda: Chain(balances, 0, fail=True), now=lambda: now)
    assert lines[-1].startswith("  Testnet:        not answering (the ledger did not answer")


async def test_the_ledger_says_when_its_newest_block_was_made():
    def answer(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/cosmos/base/tendermint/v1beta1/blocks/latest"
        return httpx.Response(
            200, json={"block": {"header": {"time": "2026-10-06T10:01:42.123456789Z"}}}
        )

    reader = LcdLedgerReader(
        "http://127.0.0.1:9", 5, client=httpx.AsyncClient(transport=httpx.MockTransport(answer))
    )
    made = datetime(2026, 10, 6, 10, 1, 42, 123000, tzinfo=UTC)
    assert await reader.latest_block_ms() == int(made.timestamp() * 1000)
    broken = LcdLedgerReader(
        "http://127.0.0.1:9",
        5,
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"block": {}}))
        ),
    )
    with pytest.raises(LedgerUnavailable, match="unexpected block response"):
        await broken.latest_block_ms()
    asyncio.get_running_loop()  # still usable
