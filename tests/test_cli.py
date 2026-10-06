import socket
import subprocess
import sys

import pytest

from hermes_fetch_ai import cli
from hermes_fetch_ai.audit import default_audit_path

TEST_IDENTITY = "cli-test-" + "identity-material-not-a-real-seed"


def test_doctor_reports_missing_config_without_traceback(tmp_path, capsys):
    assert cli.main(["doctor", "--config", str(tmp_path / "missing.yaml")]) == 1
    assert capsys.readouterr().err.startswith("config: FAIL: cannot read")


def test_doctor_names_the_config_it_checked(capsys):
    assert cli.main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "config: ok:" in out and "local-direct.yaml (the demo config" in out


def test_doctor_warns_when_seed_is_ignored(monkeypatch, capsys):
    monkeypatch.setenv("UAGENT_SEED", TEST_IDENTITY)
    assert cli.main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "seed: WARN" in out and TEST_IDENTITY not in out


def test_serve_reports_bad_config_without_traceback(tmp_path, capsys):
    assert cli.main(["serve", "--config", str(tmp_path / "missing.yaml")]) == 1
    assert "config: FAIL: cannot read" in capsys.readouterr().err


def test_serve_exits_nonzero_when_hermes_backend_cannot_start(tmp_path):
    config = tmp_path / "serve.yaml"
    config.write_text(
        "version: 1\n"
        "agent:\n"
        "  dev_random_seed: true\n"
        "hermes_mcp:\n"
        "  mode: stdio\n"
        "  command: /nonexistent/hermes-python\n"
        "  timeout_seconds: 5\n"
        "logging:\n"
        f"  audit_path: {tmp_path / 'audit.jsonl'}\n",
        encoding="utf-8",
    )
    res = subprocess.run(
        [sys.executable, "-m", "hermes_fetch_ai.cli", "serve", "--config", str(config)],
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    assert res.returncode == 1
    assert "hermes backend: FAIL" in res.stderr
    assert "command not found" in res.stderr
    assert "Traceback" not in res.stderr


def test_demo_local_runs_the_quickstart_round_trip(monkeypatch, tmp_path, capsys):
    # The demo config writes its audit log to the platform state directory.
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert cli.main(["demo", "local"]) == 0
    out = capsys.readouterr().out
    assert "visible tool count: 1" in out
    assert "echo result: hello" in out


def test_demo_local_leaves_existing_audit_logs_alone(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    real_log = default_audit_path()
    real_log.parent.mkdir(parents=True, exist_ok=True)
    real_log.write_text('{"decision": "allowed"}\n', encoding="utf-8")
    assert cli.main(["demo", "local"]) == 0
    assert real_log.read_text(encoding="utf-8") == '{"decision": "allowed"}\n'


def test_probe_hermes_fails_without_a_hermes_interpreter(capsys):
    assert cli.main(["probe-hermes"]) == 1
    out = capsys.readouterr().out
    assert "hermes_tools_server: not importable" in out
    assert "fake_tools: 2" in out


@pytest.mark.skipif(sys.platform == "win32", reason="Windows port-sharing rules differ")
def test_serve_reports_a_taken_port_without_a_traceback(tmp_path):
    with socket.socket() as busy:
        busy.bind(("0.0.0.0", 0))
        busy.listen()
        port = busy.getsockname()[1]
        config = tmp_path / "serve.yaml"
        config.write_text(
            f"version: 1\nagent:\n  dev_random_seed: true\n  port: {port}\n", encoding="utf-8"
        )
        res = subprocess.run(
            [sys.executable, "-m", "hermes_fetch_ai.cli", "serve", "--config", str(config)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    assert res.returncode == 1
    assert "serve: FAIL" in res.stderr and "already in use" in res.stderr
    assert "Traceback" not in res.stdout + res.stderr
