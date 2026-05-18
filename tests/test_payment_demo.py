from __future__ import annotations

from hermes_fetch_ai.cli import main


def test_payment_dry_run_demo(capsys):
    rc = main(["demo", "payment-dry-run", "--config", "examples/payment-dry-run.yaml"])

    out = capsys.readouterr().out

    assert rc == 0
    assert "payment dry-run: request created" in out
    assert "CompletePayment" in out
    assert "no real funds moved" in out
    assert "wallet secret" in out
    assert "operator-secret" not in out


def test_payment_alias_runs_dry_run_demo(capsys):
    rc = main(["demo", "payment", "--config", "examples/payment-dry-run.yaml"])

    out = capsys.readouterr().out

    assert rc == 0
    assert "payment dry-run: request created" in out
    assert "no real funds moved" in out
