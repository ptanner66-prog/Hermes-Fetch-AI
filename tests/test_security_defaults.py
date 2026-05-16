import subprocess
import sys

from hermes_fetch_ai.audit import AuditWriter
from hermes_fetch_ai.config import load_config


def test_hermes_backed_example_exposes_only_skills_list_publicly():
    cfg = load_config("examples/hermes-local.yaml")
    assert cfg.policy.public_tools == ["skills_list"]
    assert "skill_view" in cfg.policy.denied_tools


def test_doctor_does_not_print_seed_or_seed_fragments(monkeypatch):
    monkeypatch.setenv("UAGENT_SEED", "super_secret_seed_value_123456789")
    res = subprocess.run(
        [sys.executable, "-m", "hermes_fetch_ai.cli", "doctor"], text=True, capture_output=True
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
        reason="Bearer abcdefghijklmnopqrstuvwxyz",
    )
    text = p.read_text()
    assert "abcdefghijklmnopqrstuvwxyz" not in text
    assert "Bearer abc" not in text


def test_publish_manifest_defaults_false_in_local_configs():
    assert load_config("examples/local-direct.yaml").agent.publish_manifest is False


def test_no_hosted_network_call_in_local_demo_path(monkeypatch):
    res = subprocess.run(
        [sys.executable, "-m", "hermes_fetch_ai.cli", "demo", "local"],
        text=True,
        capture_output=True,
    )
    assert res.returncode == 0
    assert "echo result: hello" in res.stdout
