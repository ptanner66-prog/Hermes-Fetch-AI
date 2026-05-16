import pytest
from pydantic import ValidationError

from hermes_fetch_ai.config import BridgeConfig, load_config


def test_missing_seed_rejected_when_not_dev():
    with pytest.raises(ValidationError):
        BridgeConfig(agent={"dev_random_seed": False})


def test_dev_random_seed_true_accepted_without_seed():
    assert (
        BridgeConfig(agent={"dev_random_seed": True}).effective_seed().startswith("dev-ephemeral-")
    )


def test_chat_rejected():
    with pytest.raises(ValidationError, match="chat is out of v1 scope"):
        BridgeConfig(agent={"dev_random_seed": True}, chat={"enable_chat": True})


def test_stdio_requires_command():
    with pytest.raises(ValidationError, match="command"):
        BridgeConfig(agent={"dev_random_seed": True}, hermes_mcp={"mode": "stdio"})


def test_audit_path_defaults_per_platform():
    cfg = BridgeConfig(agent={"dev_random_seed": True})
    assert str(cfg.audit_path).endswith("audit.jsonl")


def test_secret_shaped_yaml_rejected(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(
        "version: 1\nagent:\n  dev_random_seed: true\n  seed: sk-abcdefghijklmnopqrstuvwxyz\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_config(p)
