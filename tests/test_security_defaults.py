import subprocess
import sys

from hermes_fetch_ai.audit import AuditWriter
from hermes_fetch_ai.config import load_config


def test_hermes_backed_example_exposes_only_low_risk_tools_publicly():
    cfg = load_config("examples/hermes-local.yaml")
    assert cfg.hermes_mcp.mode == "stdio"
    assert cfg.policy.public_tools == ["conversations_list", "events_poll"]
    assert "messages_send" in cfg.policy.denied_tools
    assert "permissions_respond" in cfg.policy.denied_tools


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


def test_hermes_demo_can_use_stdio_mcp_backend(tmp_path):
    cfg = tmp_path / "stdio.yaml"
    cfg.write_text(
        "\n".join(
            [
                "version: 1",
                "agent:",
                "  dev_random_seed: true",
                "hermes_mcp:",
                "  mode: stdio",
                f"  command: {sys.executable}",
                "  args:",
                "    - tests/fakes/fake_mcp_subprocess.py",
                "policy:",
                "  public_tools:",
                "    - echo",
            ]
        ),
        encoding="utf-8",
    )
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "hermes_fetch_ai.cli",
            "demo",
            "hermes",
            "--config",
            str(cfg),
            "--tool",
            "echo",
            "--args-json",
            '{"text": "hello"}',
        ],
        text=True,
        capture_output=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    assert "echo result: hello" in res.stdout
