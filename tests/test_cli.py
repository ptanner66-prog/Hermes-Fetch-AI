import subprocess
import sys

from hermes_fetch_ai import cli

TEST_IDENTITY = "cli-test-" + "identity-material-not-a-real-seed"


def test_doctor_reports_missing_config_without_traceback(tmp_path, capsys):
    assert cli.main(["doctor", "--config", str(tmp_path / "missing.yaml")]) == 1
    out = capsys.readouterr().out
    assert out.startswith("config: FAIL: cannot read")


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


def test_doctor_contamination_scan_passes_on_this_tree(capsys):
    assert cli.main(["doctor", "--contamination-scan"]) == 0
    assert "contamination: ok" in capsys.readouterr().out


def test_probe_hermes_reports_fake_mode(capsys):
    assert cli.main(["probe-hermes"]) == 0
    assert "fake_mode: ok" in capsys.readouterr().out
