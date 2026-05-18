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


def test_yaml_seed_rejected_even_if_dev_prefixed(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(
        "version: 1\nagent:\n  dev_random_seed: true\n  seed: dev-fixed-review-seed\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="seed"):
        load_config(p)


def test_direct_agent_seed_rejected(monkeypatch):
    monkeypatch.setenv("UAGENT_SEED", "operator-supplied-test-seed")

    with pytest.raises(ValidationError, match="UAGENT_SEED"):
        BridgeConfig(agent={"dev_random_seed": False, "seed": "stable-local-review-seed"})


def test_stdio_command_expands_nonsecret_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_FETCH_HERMES_PYTHON", "python-from-env")
    p = tmp_path / "c.yaml"
    p.write_text(
        "\n".join(
            [
                "version: 1",
                "agent:",
                "  dev_random_seed: true",
                "hermes_mcp:",
                "  mode: stdio",
                "  command: ${HERMES_FETCH_HERMES_PYTHON}",
                "  args:",
                "    - -m",
                "    - hermes_cli.main",
            ]
        ),
        encoding="utf-8",
    )
    cfg = load_config(p)
    assert cfg.hermes_mcp.command == "python-from-env"


def test_missing_stdio_env_var_fails_config(monkeypatch):
    monkeypatch.delenv("HERMES_FETCH_HERMES_PYTHON", raising=False)

    with pytest.raises(ValueError, match="HERMES_FETCH_HERMES_PYTHON"):
        load_config("examples/hermes-stdio-env.yaml")


def test_secret_env_var_name_not_expanded(tmp_path, monkeypatch):
    monkeypatch.setenv("API_KEY", "not-used")
    p = tmp_path / "c.yaml"
    p.write_text(
        "\n".join(
            [
                "version: 1",
                "agent:",
                "  dev_random_seed: true",
                "hermes_mcp:",
                "  mode: stdio",
                "  command: ${API_KEY}",
                "  args:",
                "    - mcp",
                "    - serve",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="secret-shaped environment"):
        load_config(p)


def test_secret_env_var_value_not_expanded(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_FETCH_HERMES_PYTHON", "sk-abcdefghijklmnopqrstuvwxyz")
    p = tmp_path / "c.yaml"
    p.write_text(
        "\n".join(
            [
                "version: 1",
                "agent:",
                "  dev_random_seed: true",
                "hermes_mcp:",
                "  mode: stdio",
                "  command: ${HERMES_FETCH_HERMES_PYTHON}",
                "  args:",
                "    - mcp",
                "    - serve",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="environment expansion"):
        load_config(p)


def test_mailbox_config_can_be_loaded_for_static_checks_without_runtime_seed(monkeypatch):
    monkeypatch.delenv("UAGENT_SEED", raising=False)
    monkeypatch.setenv("HERMES_FETCH_HERMES_PYTHON", "python")

    cfg = load_config("examples/agentverse-mailbox-hermes.yaml", require_runtime_secrets=False)

    assert cfg.agent.mode == "mailbox"
    assert cfg.agent.dev_random_seed is False


def test_static_loaded_mailbox_config_effective_seed_still_fails_closed(monkeypatch):
    monkeypatch.delenv("UAGENT_SEED", raising=False)
    monkeypatch.setenv("HERMES_FETCH_HERMES_PYTHON", "python")

    cfg = load_config("examples/agentverse-mailbox-hermes.yaml", require_runtime_secrets=False)

    with pytest.raises(ValueError, match="UAGENT_SEED"):
        cfg.effective_seed()


def test_whitespace_runtime_seed_rejected(monkeypatch):
    monkeypatch.setenv("UAGENT_SEED", "   ")

    with pytest.raises(ValidationError, match="UAGENT_SEED"):
        BridgeConfig(agent={"dev_random_seed": False})


def test_proxy_mode_rejects_dev_random_seed():
    with pytest.raises(ValidationError, match="stable UAGENT_SEED"):
        BridgeConfig(agent={"mode": "proxy", "dev_random_seed": True})
