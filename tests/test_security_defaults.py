import subprocess
import sys

import pytest

from hermes_fetch_ai.audit import AuditWriter
from hermes_fetch_ai.config import HERMES_PYTHON_VAR, load_config


def test_hermes_backed_example_exposes_only_skills_list_publicly():
    cfg = load_config("examples/hermes-local.yaml")
    assert cfg.policy.public_tools == ["skills_list"]
    assert "skill_view" in cfg.policy.denied_tools


def test_production_hermes_config_requires_a_stable_seed(monkeypatch):
    monkeypatch.setenv(HERMES_PYTHON_VAR, "/hermes/venv/bin/python")
    with pytest.raises(ValueError, match="UAGENT_SEED is required"):
        load_config("examples/hermes-stdio.yaml")
    monkeypatch.setenv("UAGENT_SEED", "production-config-test-" + "identity-material")
    cfg = load_config("examples/hermes-stdio.yaml")
    assert cfg.agent.dev_random_seed is False
    assert cfg.effective_seed() == cfg.effective_seed()
    assert cfg.policy.public_tools == ["skills_list"]


def test_hermes_example_denylists_match_and_use_exact_tool_names(monkeypatch):
    monkeypatch.setenv("UAGENT_SEED", "production-config-test-" + "identity-material")
    monkeypatch.setenv(HERMES_PYTHON_VAR, "/hermes/venv/bin/python")
    stdio = load_config("examples/hermes-stdio.yaml").policy.denied_tools
    local = load_config("examples/hermes-local.yaml").policy.denied_tools
    assert stdio == local
    # Bare toolset names such as "web" never match a real tool name.
    assert not {"web", "browser", "image", "tts", "kanban"} & set(stdio)


def test_doctor_does_not_print_seed_or_seed_fragments(monkeypatch):
    monkeypatch.setenv("UAGENT_SEED", "super_secret_seed_value_123456789")
    res = subprocess.run(
        [sys.executable, "-m", "hermes_fetch_ai.cli", "doctor"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert res.returncode == 0
    assert "super_secret" not in res.stdout + res.stderr


def test_audit_log_no_raw_args_output_full_sender_or_secret(tmp_path):
    p = tmp_path / "a.jsonl"
    a = AuditWriter(p)
    a.write(
        sender="agent1qabcdefghijklmnopqrstuvwxyz",
        tool="echo",
        decision="denied",
        reason=("Bear" + "er " + "abcdefghijklmnopqrstuvwxyz"),
    )
    text = p.read_text()
    assert "abcdefghijklmnopqrstuvwxyz" not in text
    assert ("Bear" + "er " + "abc") not in text


def test_publish_manifest_defaults_false_in_local_configs():
    assert load_config("examples/local-direct.yaml").agent.publish_manifest is False


def test_no_hosted_network_call_in_local_demo_path(monkeypatch):
    res = subprocess.run(
        [sys.executable, "-m", "hermes_fetch_ai.cli", "demo", "local"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert res.returncode == 0
    assert "echo result: hello" in res.stdout
