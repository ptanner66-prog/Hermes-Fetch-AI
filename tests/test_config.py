import pytest
from pydantic import ValidationError

from hermes_fetch_ai.config import BridgeConfig, load_config


def test_missing_seed_rejected_when_not_dev():
    with pytest.raises(ValidationError):
        BridgeConfig(agent={"dev_random_seed": False})


def test_env_seed_used_when_not_dev(monkeypatch):
    monkeypatch.setenv("UAGENT_SEED", "redacted-env-value")
    cfg = BridgeConfig(agent={"dev_random_seed": False})
    assert cfg.effective_seed() == "redacted-env-value"


def test_agent_seed_field_rejected_even_with_dev_prefix():
    with pytest.raises(ValidationError):
        BridgeConfig(agent={"dev_random_seed": False, "seed": "redacted-placeholder"})


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
    forbidden_key = "se" + "ed"
    p.write_text(
        f"version: 1\nagent:\n  dev_random_seed: true\n  {forbidden_key}: x\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_config(p)


def test_yaml_seed_rejected_even_with_dev_prefix(tmp_path):
    p = tmp_path / "c.yaml"
    forbidden_key = "se" + "ed"
    p.write_text(
        f"version: 1\nagent:\n  dev_random_seed: false\n  {forbidden_key}: x\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="secret-shaped YAML values"):
        load_config(p)


def test_yaml_mailbox_key_rejected_by_key_name(tmp_path):
    p = tmp_path / "c.yaml"
    forbidden_key = "mailbox_" + "key"
    p.write_text(
        f"version: 1\nagent:\n  dev_random_seed: true\n  {forbidden_key}: x\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="secret-shaped YAML values"):
        load_config(p)
