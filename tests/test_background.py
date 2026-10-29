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
import psutil
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
        with log.open("ab") as f:
            f.write(b"one\r\ntwo\n")  # a log written on Windows ends lines with \r\n

    threading.Thread(target=write).start()
    with pytest.raises(KeyboardInterrupt):
        background.follow(log, out, poll=0.02)
    assert seen == ["one", "two"]


def test_serve_stops_when_the_stop_file_appears(tmp_path, seed, unused_tcp_port):
    config = write_config(tmp_path, unused_tcp_port)
    state = tmp_path / "state"
    log_path = tmp_path / "serve-output.log"
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            [sys.executable, "-m", "hermes_fetch_ai.cli", "serve", "--config", str(config)],
            env=dict(os.environ),
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + background.START_WAIT_SECONDS
            while read_running(state) is None and time.monotonic() < deadline:
                assert proc.poll() is None, log_path.read_text(encoding="utf-8", errors="replace")
                time.sleep(0.1)
            info = read_running(state)
            assert info is not None, log_path.read_text(encoding="utf-8", errors="replace")
            background.request_stop(state, info)
            assert proc.wait(background.STOP_WAIT_SECONDS) == 0, log_path.read_text(
                encoding="utf-8", errors="replace"
            )
        finally:
            if proc.poll() is None:
                kill_test_tree(proc)
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


def kill_test_tree(process):
    """The Windows venv executable is a launcher; stop its interpreter too."""
    try:
        children = psutil.Process(process.pid).children(recursive=True)
    except psutil.NoSuchProcess:
        children = []
    for child in reversed(children):
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    process.kill()
    process.wait(timeout=10)
    _, alive = psutil.wait_procs(children, timeout=10)
    assert not alive, "test interpreter children did not exit"


@pytest.mark.parametrize("remove_metadata", [False, True])
def test_claim_holds_a_process_lock_and_crash_releases_it(tmp_path, remove_metadata):
    script = tmp_path / "claim.py"
    script.write_text(
        "from pathlib import Path\n"
        "import sys, time\n"
        "from hermes_fetch_ai.background import claim\n"
        "state = Path(sys.argv[1])\n"
        "claim(state, state / 'config.yaml')\n"
        "(state / 'claimed').write_text('ready')\n"
        "time.sleep(60)\n"
    )
    state = tmp_path / "state"
    owner = subprocess.Popen([sys.executable, str(script), str(state)])
    try:
        deadline = time.monotonic() + 20
        while not (state / "claimed").exists() and time.monotonic() < deadline:
            assert owner.poll() is None
            time.sleep(0.05)
        assert (state / "claimed").exists()
        if remove_metadata:
            (state / RUN_FILE).unlink()
        with pytest.raises(AlreadyRunning):
            claim(state, tmp_path / "other.yaml")
    finally:
        kill_test_tree(owner)
    # No release() ran: the operating system releases ownership on a crash.
    info = claim(state, tmp_path / "replacement.yaml")
    try:
        assert info.pid == os.getpid()
    finally:
        release(state)


def test_concurrent_claimants_cannot_both_start(tmp_path):
    script = tmp_path / "race.py"
    script.write_text(
        "from pathlib import Path\n"
        "import sys, time\n"
        "from hermes_fetch_ai import background\n"
        "root = Path(sys.argv[1]); name = sys.argv[2]\n"
        "write = background._write_run_file\n"
        "def slow_write(*args):\n"
        "    time.sleep(0.25)\n"
        "    write(*args)\n"
        "background._write_run_file = slow_write\n"
        "(root / (name + '.waiting')).touch()\n"
        "while not (root / 'go').exists(): time.sleep(0.01)\n"
        "try:\n"
        "    background.claim(root / 'state', root / 'config.yaml')\n"
        "    result = 'owner'\n"
        "except background.AlreadyRunning:\n"
        "    result = 'refused'\n"
        "(root / (name + '.result')).write_text(result)\n"
        "time.sleep(60)\n"
    )
    contenders = [
        subprocess.Popen([sys.executable, str(script), str(tmp_path), str(n)]) for n in range(3)
    ]
    try:
        deadline = time.monotonic() + 30
        while len(list(tmp_path.glob("*.waiting"))) < 3 and time.monotonic() < deadline:
            time.sleep(0.05)
        assert len(list(tmp_path.glob("*.waiting"))) == 3
        (tmp_path / "go").touch()
        while len(list(tmp_path.glob("*.result"))) < 3 and time.monotonic() < deadline:
            time.sleep(0.05)
        results = [path.read_text() for path in tmp_path.glob("*.result")]
        assert sorted(results) == ["owner", "refused", "refused"]
    finally:
        for process in contenders:
            kill_test_tree(process)


def test_stop_does_not_signal_a_reused_pid(tmp_path):
    stranger = sleeper()
    try:
        # It even has the old bridge's command line, but is a new process.
        run = {
            "pid": stranger.pid,
            "started": time.time() - 60,
            "created": psutil.Process(stranger.pid).create_time() - 60,
            "config": "old.yaml",
        }
        (tmp_path / RUN_FILE).write_text(json.dumps(run))
        assert background.stop(tmp_path, wait=0) == 0
        assert stranger.poll() is None
        assert not (tmp_path / STOP_FILE).exists()
    finally:
        stranger.kill()
        stranger.wait(timeout=10)


@pytest.mark.parametrize("payload", ["stop", "{}", "null", "[]"])
def test_legacy_or_malformed_stop_requests_cannot_stop_a_bridge(tmp_path, payload):
    (tmp_path / STOP_FILE).write_text(payload)
    assert not background.stop_requested(tmp_path)


def test_a_stop_request_for_a_previous_process_cannot_stop_its_successor(tmp_path):
    info = claim(tmp_path, tmp_path / "config.yaml")
    try:
        stale = background.RunInfo(
            pid=info.pid,
            started=info.started - 60,
            created=info.created - 60,
            config=info.config,
        )
        background.request_stop(tmp_path, stale)
        assert not background.stop_requested(tmp_path)
        background.request_stop(tmp_path, info)
        assert background.stop_requested(tmp_path)
    finally:
        release(tmp_path)
