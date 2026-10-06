import pytest
from pydantic import ValidationError

from hermes_fetch_ai.config import (
    HERMES_PYTHON_VAR,
    BridgeConfig,
    ConfigError,
    format_validation_error,
    load_config,
    validate_config_file,
)


def test_missing_seed_rejected_when_not_dev():
    with pytest.raises(ValidationError):
        BridgeConfig(agent={"dev_random_seed": False})


LONG_TEST_IDENTITY = "redacted-env-value-for-tests-" + "0123456789abcdef"


def test_env_seed_used_when_not_dev(monkeypatch):
    monkeypatch.setenv("UAGENT_SEED", LONG_TEST_IDENTITY)
    cfg = BridgeConfig(agent={"dev_random_seed": False})
    assert cfg.effective_seed() == LONG_TEST_IDENTITY


def test_short_seed_rejected_without_echoing_it(monkeypatch):
    short = "tiny-" + "value"
    monkeypatch.setenv("UAGENT_SEED", short)
    with pytest.raises(ValidationError, match="at least 32 characters") as exc:
        BridgeConfig(agent={"dev_random_seed": False})
    assert short not in format_validation_error(exc.value)


def test_ignored_seed_is_reported(monkeypatch):
    cfg = BridgeConfig(agent={"dev_random_seed": True})
    assert cfg.ignored_seed_warning() is None
    monkeypatch.setenv("UAGENT_SEED", LONG_TEST_IDENTITY)
    warning = cfg.ignored_seed_warning()
    assert warning and "dev_random_seed" in warning
    assert LONG_TEST_IDENTITY not in warning


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


def test_stdio_command_can_come_from_the_hermes_plugin(monkeypatch):
    with pytest.raises(ValidationError, match="hermes fetchai-bridge"):
        BridgeConfig(agent={"dev_random_seed": True}, hermes_mcp={"mode": "stdio"})
    monkeypatch.setenv(HERMES_PYTHON_VAR, "/hermes/venv/bin/python")
    cfg = BridgeConfig(agent={"dev_random_seed": True}, hermes_mcp={"mode": "stdio"})
    assert cfg.hermes_mcp.command is None


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


def _write(tmp_path, body):
    p = tmp_path / "c.yaml"
    p.write_text("version: 1\nagent:\n  dev_random_seed: true\n" + body, encoding="utf-8")
    return p


@pytest.mark.parametrize(
    "body",
    [
        # A credential inside a list (previously never scanned).
        'hermes_mcp:\n  mode: stdio\n  command: python\n  args: ["s' + 'k-live-abcdefghijklmnop12"]\n',
        # A command-line flag that introduces a secret.
        'hermes_mcp:\n  mode: stdio\n  command: python\n  args: ["--api-' + 'key", "x"]\n',
        # key=value assignments anywhere in a value.
        'hermes_mcp:\n  mode: stdio\n  command: python\n  args: ["--opt", "tok' + 'en=abc"]\n',
        "logging:\n  audit_path: /tmp/a.jsonl?pass" + "word=x\n",
    ],
)
def test_secret_shaped_values_rejected_anywhere(tmp_path, body):
    with pytest.raises(ValueError, match="secret-shaped YAML values"):
        load_config(_write(tmp_path, body))


def test_tool_names_resembling_secrets_are_not_flagged(tmp_path):
    cfg = load_config(_write(tmp_path, "policy:\n  public_tools: [task-list, count_tokens]\n"))
    assert cfg.policy.public_tools == ["task-list", "count_tokens"]


def test_prose_mentioning_tokens_is_not_flagged(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(
        'version: 1\nagent:\n  dev_random_seed: true\n  description: "Bridge for token-gated tools"\n',
        encoding="utf-8",
    )
    assert load_config(p).agent.description == "Bridge for token-gated tools"


def test_missing_config_reports_cleanly(tmp_path):
    with pytest.raises(ConfigError, match="cannot read"):
        load_config(tmp_path / "missing.yaml")
    ok, msg = validate_config_file(tmp_path / "missing.yaml")
    assert not ok and "cannot read" in msg


def test_malformed_yaml_reports_location(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("version: 1\nagent: [unclosed\n", encoding="utf-8")
    ok, msg = validate_config_file(p)
    assert not ok and "invalid YAML" in msg and "line" in msg


def test_validation_errors_are_summarized_without_input_dump():
    ok, msg = True, ""
    try:
        BridgeConfig(agent={"dev_random_seed": False})
    except ValidationError as exc:
        ok, msg = False, format_validation_error(exc)
    assert not ok
    assert msg == "UAGENT_SEED is required when agent.dev_random_seed=false"
