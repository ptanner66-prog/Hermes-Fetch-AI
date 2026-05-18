from __future__ import annotations

from pathlib import Path

import pytest
from uagents_core.contrib.protocols.payment import CommitPayment, Funds, payment_protocol_spec

from hermes_fetch_ai.config import load_config
from hermes_fetch_ai.payment_policy import is_payment_required
from hermes_fetch_ai.payments import PaymentDryRunStore, dryrun_transaction_id


def test_payment_defaults_disabled():
    cfg = load_config(Path("examples/local-direct.yaml"))
    assert cfg.payment.mode == "disabled"
    assert not is_payment_required(cfg, "echo")


def test_payment_dry_run_config_uses_official_models():
    cfg = load_config(Path("examples/payment-dry-run.yaml"))
    assert cfg.payment.mode == "dry_run"
    assert payment_protocol_spec.name == "AgentPaymentProtocol"
    assert payment_protocol_spec.version == "0.1.0"
    assert Funds(amount="1", currency="FET").payment_method == "fet_direct"
    assert is_payment_required(cfg, "echo")


def test_payment_dry_run_request_commit_complete_without_network():
    cfg = load_config(Path("examples/payment-dry-run.yaml"))
    store = PaymentDryRunStore()
    request = store.request(cfg, "agent1sender", "echo", "agent1bridge")
    assert request.reference
    assert request.accepted_funds[0].payment_method == "fet_direct"
    commit = CommitPayment(
        funds=request.accepted_funds[0],
        recipient=request.recipient,
        transaction_id=dryrun_transaction_id(),
        reference=request.reference,
    )
    complete = store.commit("agent1sender", commit)
    assert complete.__class__.__name__ == "CompletePayment"
    assert complete.transaction_id.startswith("dryrun-")


def test_payment_dry_run_store_rejects_non_dry_run_configs():
    cfg = load_config(Path("examples/local-direct.yaml"))
    store = PaymentDryRunStore()

    with pytest.raises(ValueError, match="dry_run"):
        store.request(cfg, "agent1sender", "echo", "agent1bridge")


def test_payment_dry_run_rejects_real_shaped_transaction_id():
    cfg = load_config(Path("examples/payment-dry-run.yaml"))
    store = PaymentDryRunStore()
    request = store.request(cfg, "agent1sender", "echo", "agent1bridge")
    commit = CommitPayment(
        funds=request.accepted_funds[0],
        recipient=request.recipient,
        transaction_id="0x" + "a" * 64,
        reference=request.reference,
    )
    cancel = store.commit("agent1sender", commit)
    assert cancel.__class__.__name__ == "CancelPayment"
    assert "dryrun" in (cancel.reason or "")


def test_payment_unknown_reference_never_echoes_full_transaction_id():
    cfg = load_config(Path("examples/payment-dry-run.yaml"))
    store = PaymentDryRunStore()
    request = store.request(cfg, "agent1sender", "echo", "agent1bridge")
    transaction_id = "0x" + "a" * 64
    commit = CommitPayment(
        funds=request.accepted_funds[0],
        recipient=request.recipient,
        transaction_id=transaction_id,
        reference="hfa-unknown-reference",
    )

    cancel = store.commit("agent1sender", commit)

    assert cancel.__class__.__name__ == "CancelPayment"
    assert cancel.transaction_id != transaction_id
    assert len(cancel.transaction_id or "") <= 18
    assert "dryrun" in (cancel.reason or "")


def test_testnet_payment_mode_is_operator_stop(tmp_path):
    cfg_path = tmp_path / "testnet.yaml"
    cfg_path.write_text(
        """
version: 1
agent:
  dev_random_seed: true
payment:
  mode: testnet
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="operator stop"):
        load_config(cfg_path)


def test_real_operator_approved_is_an_operator_stop(tmp_path):
    cfg_path = tmp_path / "real.yaml"
    cfg_path.write_text(
        """
version: 1
agent:
  dev_random_seed: true
payment:
  mode: real_operator_approved
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="operator stop"):
        load_config(cfg_path)


def test_payment_secret_shaped_yaml_is_rejected(tmp_path):
    cfg_path = tmp_path / "secret.yaml"
    cfg_path.write_text(
        """
version: 1
agent:
  dev_random_seed: true
payment:
  mode: dry_run
  private_key: not-allowed
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="secret-shaped YAML"):
        load_config(cfg_path)
