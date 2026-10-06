"""The CLI's selling commands, offline (the ledger is faked where one is needed)."""

import json
import os
import sys
import textwrap

import pytest

from hermes_fetch_ai import cli
from hermes_fetch_ai.ledger import LcdLedgerReader, LedgerUnavailable
from hermes_fetch_ai.wallet import agent_address, wallet_address

SEED = "cli-paid-test-" + "identity-material-not-a-real-seed"
PAYOUT = "fetch1hh09pm44murgmu7rpaxluwad3way3nxq0fl6fx"


@pytest.fixture
def paid_config(tmp_path, monkeypatch):
    monkeypatch.setenv("UAGENT_SEED", SEED)
    path = tmp_path / "paid.yaml"
    path.write_text(
        textwrap.dedent(
            f"""
            agent: {{name: cli_seller}}
            hermes_mcp: {{mode: fake}}
            payments: {{enabled: true, state_dir: {json.dumps(str(tmp_path / "state"))}}}
            services:
              research:
                title: Research a topic
                description: Finds sources.
                price: "0.05"
                runner: {{type: echo}}
            """
        )
    )
    return str(path)


def test_demo_paid_walks_through_a_sale(capsys):
    assert cli.main(["demo", "paid"]) == 0
    out = capsys.readouterr().out
    assert "price: 0.05 testnet FET" in out
    assert "answer: hello" in out
    assert "same payment from another agent: quote does not match this call" in out
    assert "same payment from the buyer: the same answer, without running" in out


def test_doctor_reports_payments(paid_config, capsys):
    assert cli.main(["doctor", "--config", paid_config]) == 0
    assert (
        "payments: on (testnet, dorado-1); services: research 0.05 FET" in capsys.readouterr().out
    )
    assert cli.main(["doctor"]) == 0
    assert "payments: off" in capsys.readouterr().out


def test_wallet_shows_addresses_without_network(paid_config, capsys):
    assert cli.main(["wallet", "--config", paid_config]) == 0
    out = capsys.readouterr().out
    assert f"agent address: {agent_address(SEED)}" in out
    assert f"income wallet: {wallet_address(SEED)} (the agent's own wallet)" in out
    assert SEED not in out


def test_wallet_balance_asks_the_ledger(paid_config, monkeypatch, capsys):
    async def balance(self, address, denom):
        assert (address, denom) == (wallet_address(SEED), "atestfet")
        return 1_500_000_000_000_000_000

    monkeypatch.setattr(LcdLedgerReader, "balance", balance)
    assert cli.main(["wallet", "--config", paid_config, "--balance"]) == 0
    assert "balance: 1.5 testnet FET" in capsys.readouterr().out

    async def down(self, address, denom):
        raise LedgerUnavailable("the ledger did not answer (ConnectError)")

    monkeypatch.setattr(LcdLedgerReader, "balance", down)
    assert cli.main(["wallet", "--config", paid_config, "--balance"]) == 1
    assert "balance: FAIL" in capsys.readouterr().err


def test_wallet_needs_a_stable_identity(tmp_path, capsys):
    path = tmp_path / "dev.yaml"
    path.write_text("agent: {dev_random_seed: true}\n")
    assert cli.main(["wallet", "--config", str(path)]) == 1
    assert "dev_random_seed: true" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("chain", "error", "code", "expected"),
    [
        ("dorado-1", None, 0, "ledger: ok: dorado-1"),
        ("fetchhub-4", None, 1, "not 'dorado-1'"),
        (None, LedgerUnavailable("the ledger did not answer (HTTP 503)"), 1, "HTTP 503"),
    ],
)
def test_ledger_check(paid_config, monkeypatch, capsys, chain, error, code, expected):
    async def chain_id(self):
        if error:
            raise error
        return chain

    monkeypatch.setattr(LcdLedgerReader, "chain_id", chain_id)
    assert cli.main(["ledger", "--config", paid_config]) == code
    captured = capsys.readouterr()
    assert expected in captured.out + captured.err


def test_seller_controls(paid_config, capsys):
    assert cli.main(["seller", "credits", "--config", paid_config]) == 0
    assert "selling: on" in capsys.readouterr().out
    assert cli.main(["seller", "pause", "--config", paid_config]) == 0
    assert (
        cli.main(["seller", "ban", "agent1qspam", "--reason", "spam", "--config", paid_config]) == 0
    )
    assert cli.main(["seller", "credits", "--config", paid_config]) == 0
    out = capsys.readouterr().out
    assert "selling: paused" in out and "banned: agent1qspam (spam)" in out
    assert "no payments recorded" in out
    assert cli.main(["seller", "unban", "agent1qspam", "--config", paid_config]) == 0
    assert cli.main(["seller", "unban", "agent1qspam", "--config", paid_config]) == 0
    assert cli.main(["seller", "resume", "--config", paid_config]) == 0
    out = capsys.readouterr().out
    assert "unbanned" in out and "was not banned" in out and "selling again" in out


def test_seller_ban_needs_an_address(paid_config, capsys):
    assert cli.main(["seller", "ban", "--config", paid_config]) == 2
    assert "needs the agent address" in capsys.readouterr().err


def test_seller_needs_payments_on(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("UAGENT_SEED", SEED)
    path = tmp_path / "free.yaml"
    path.write_text("agent: {name: free}\n")
    assert cli.main(["seller", "credits", "--config", str(path)]) == 1
    assert "payments are off" in capsys.readouterr().err


def test_seller_lists_payments(paid_config, capsys):
    from hermes_fetch_ai.config import load_config
    from hermes_fetch_ai.store import QuoteAlreadyPaid, Store
    from hermes_fetch_ai.uagent_app import payment_store_path

    store = Store.open(payment_store_path(load_config(paid_config), SEED))
    store.record_payment(
        reference="hfq1.example",
        kind="call",
        sender="agent1qbuyer",
        subject="research",
        digest="d",
        amount_base=50_000_000_000_000_000,
        tx_hash="9EDD34AB91C3D45DAB43A0B2A25125519AED7EA1BB30F3D5B2D8E58F9FACB496",
        payer=PAYOUT,
        block_time_ms=1,
        height=1,
        quoted_ms=1,
        now_ms=2,
    )
    with pytest.raises(QuoteAlreadyPaid):
        store.record_payment(
            reference="hfq1.example",
            kind="call",
            sender="agent1qbuyer",
            subject="research",
            digest="d",
            amount_base=50_000_000_000_000_000,
            tx_hash="1" * 64,
            payer=PAYOUT,
            block_time_ms=2,
            height=2,
            quoted_ms=1,
            now_ms=3,
        )
    store.close()
    assert cli.main(["seller", "credits", "--config", paid_config]) == 0
    out = capsys.readouterr().out
    # Recorded long ago (now_ms=2), so listing marks it lapsed: never used in its window.
    assert "lapsed" in out and "0.05 FET" in out and "research" in out and "9EDD34AB…B496" in out
    assert f"extra payment, refund it: 0.05 FET  tx 11111111…1111  payer {PAYOUT}" in out


def command_service_config(tmp_path, argv):
    path = tmp_path / "command.yaml"
    path.write_text(
        textwrap.dedent(
            f"""
            agent: {{name: cli_seller}}
            payments: {{enabled: true, state_dir: {json.dumps(str(tmp_path / "state"))}}}
            services:
              svc:
                title: A service
                description: Runs a program.
                price: "0.01"
                runner: {{type: command, argv: {json.dumps([str(a) for a in argv])}}}
            """
        )
    )
    return str(path)


def test_missing_programs_fail_doctor_and_serve(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("UAGENT_SEED", SEED)
    missing = tmp_path / "no-such-program"
    path = command_service_config(tmp_path, [missing])
    assert cli.main(["doctor", "--config", path]) == 1
    assert f"services: FAIL: service svc: program {missing} not found" in capsys.readouterr().err
    # serve refuses before starting anything: a program that cannot run would take payments.
    assert cli.main(["serve", "--config", path]) == 1
    assert "not found" in capsys.readouterr().err
    script = tmp_path / "gone.py"
    path = command_service_config(tmp_path, [sys.executable, script])
    assert cli.main(["doctor", "--config", path]) == 1
    assert f"service svc: {script} not found" in capsys.readouterr().err


@pytest.mark.skipif(os.name == "nt", reason="Windows has no execute permission bit")
def test_programs_must_be_executable(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("UAGENT_SEED", SEED)
    program = tmp_path / "program"
    program.write_text("#!/bin/sh\necho hi\n")
    program.chmod(0o644)
    assert cli.main(["doctor", "--config", command_service_config(tmp_path, [program])]) == 1
    assert "is not executable" in capsys.readouterr().err


def test_seller_try_runs_a_service_unpaid(paid_config, capsys):
    args = ["seller", "try", "research", "--request", "tides", "--config", paid_config]
    assert cli.main(args) == 0
    assert capsys.readouterr().out.strip() == "tides"


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        ([], "try needs a service name (configured: research)"),
        (["nope", "--request", "x"], "try needs a service name"),
        (["research"], "try needs --request"),
    ],
)
def test_seller_try_needs_a_service_and_a_request(paid_config, capsys, extra, expected):
    assert cli.main(["seller", "try", *extra, "--config", paid_config]) == 2
    assert expected in capsys.readouterr().err


def test_seller_try_reports_a_failing_program(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("UAGENT_SEED", SEED)
    script = tmp_path / "fail.py"
    script.write_text(
        "import sys\nprint('model server unreachable', file=sys.stderr)\nsys.exit(3)\n"
    )
    path = command_service_config(tmp_path, [sys.executable, script])
    assert cli.main(["seller", "try", "svc", "--request", "x", "--config", path]) == 1
    assert "svc: the service program failed (exit 3)" in capsys.readouterr().err


def test_seller_backup_copies_the_records(paid_config, tmp_path, capsys):
    import sqlite3

    assert cli.main(["seller", "ban", "agent1qspam", "--config", paid_config]) == 0
    target = tmp_path / "backup.sqlite3"
    assert cli.main(["seller", "backup", "--to", str(target), "--config", paid_config]) == 0
    assert f"copied to {target}" in capsys.readouterr().out
    copy = sqlite3.connect(target)
    try:
        assert copy.execute("SELECT sender FROM banned").fetchall() == [("agent1qspam",)]
    finally:
        copy.close()
    if os.name != "nt":
        assert target.stat().st_mode & 0o077 == 0
    # Never overwrites, and needs a destination.
    assert cli.main(["seller", "backup", "--to", str(target), "--config", paid_config]) == 1
    assert "already exists" in capsys.readouterr().err
    assert cli.main(["seller", "backup", "--config", paid_config]) == 2
    assert "backup needs --to" in capsys.readouterr().err
