from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from hermes_fetch_ai.cli import main
from hermes_fetch_ai.config import validate_config_file
from hermes_fetch_ai.uagent_app import run_bridge_for


def test_mailbox_config_requires_env_seed(monkeypatch):
    monkeypatch.delenv("UAGENT_SEED", raising=False)
    monkeypatch.setenv("HERMES_FETCH_HERMES_PYTHON", "python")

    ok, msg = validate_config_file(Path("examples/agentverse-mailbox-hermes.yaml"))

    assert not ok
    assert "UAGENT_SEED" in msg


def test_mailbox_config_validates_with_env_seed(monkeypatch):
    monkeypatch.setenv("UAGENT_SEED", "operator-supplied-test-seed")
    monkeypatch.setenv("HERMES_FETCH_HERMES_PYTHON", "python")

    ok, msg = validate_config_file(Path("examples/agentverse-mailbox-hermes.yaml"))

    assert ok, msg


def test_doctor_probe_backend_does_not_require_runtime_seed(monkeypatch, capsys):
    async def fake_probe_backend(config_path):
        assert config_path == "examples/agentverse-mailbox-hermes.yaml"
        return True, "fake tools"

    monkeypatch.delenv("UAGENT_SEED", raising=False)
    monkeypatch.setenv("HERMES_FETCH_HERMES_PYTHON", "python")
    monkeypatch.setattr("hermes_fetch_ai.cli._probe_backend", fake_probe_backend)

    rc = main(["doctor", "--config", "examples/agentverse-mailbox-hermes.yaml", "--probe-backend"])

    out = capsys.readouterr().out
    assert rc == 0
    assert "backend: ok: fake tools" in out


def test_demo_mailbox_rejects_non_mailbox_config(capsys):
    rc = main(
        ["demo", "mailbox", "--config", "examples/local-direct.yaml", "--duration-seconds", "1"]
    )

    out = capsys.readouterr().out

    assert rc == 1
    assert "config agent.mode must be mailbox" in out


def test_demo_mailbox_validation_does_not_print_seed(monkeypatch, capsys):
    seed = "operator-secret-seed-should-not-print"
    monkeypatch.setenv("UAGENT_SEED", seed)

    rc = main(
        ["demo", "mailbox", "--config", "examples/local-direct.yaml", "--duration-seconds", "1"]
    )

    out = capsys.readouterr().out

    assert rc == 1
    assert seed not in out


def test_demo_mailbox_points_to_hermes_python_when_that_env_is_missing(monkeypatch, capsys):
    monkeypatch.setenv("UAGENT_SEED", "operator-secret-seed-should-not-print")
    monkeypatch.delenv("HERMES_FETCH_HERMES_PYTHON", raising=False)

    rc = main(
        [
            "demo",
            "mailbox",
            "--config",
            "examples/agentverse-mailbox-hermes.yaml",
            "--duration-seconds",
            "1",
        ]
    )

    out = capsys.readouterr().out

    assert rc == 1
    assert "HERMES_FETCH_HERMES_PYTHON" in out
    assert "operator-secret-seed-should-not-print" not in out


def test_demo_hermes_fails_when_tool_call_errors(monkeypatch, capsys):
    async def fake_roundtrip(cfg, tool, args):
        return ("agent1fakebridge", 1, "", "tool execution failed", 1)

    monkeypatch.setattr("hermes_fetch_ai.cli.run_local_tool_roundtrip", fake_roundtrip)

    rc = main(["demo", "hermes", "--config", "examples/local-direct.yaml"])

    out = capsys.readouterr().out
    assert rc == 1
    assert "tool execution failed" in out


def test_run_bridge_for_returns_address_without_printing(monkeypatch):
    from hermes_fetch_ai import uagent_app
    from hermes_fetch_ai.config import load_config

    captured = {}

    class FakeAgent:
        address = "agent1fakebridge"

        def __init__(self, **kwargs):
            captured.update(kwargs)

        def include(self, *args, **kwargs):
            return None

        def run(self):
            return None

    fake_cosmpy_protos = str(Path(".venv/Lib/site-packages/cosmpy/protos"))
    monkeypatch.syspath_prepend(fake_cosmpy_protos)

    class ReadyProcess:
        exitcode = None

        def __init__(self, target=None, args=(), daemon=None):
            self.ready_conn = args[1]
            self._alive = True

        def start(self):
            assert all(
                not p.replace("\\", "/").lower().rstrip("/").endswith("/cosmpy/protos")
                for p in sys.path
            )
            self.ready_conn.send({"status": "ready", "address": "agent1fakebridge"})

        def is_alive(self):
            return self._alive

        def terminate(self):
            self._alive = False

        def join(self, timeout=None):
            return None

    monkeypatch.setattr(uagent_app, "Agent", FakeAgent)
    monkeypatch.setattr(uagent_app.multiprocessing, "Process", ReadyProcess)
    monkeypatch.setenv("UAGENT_SEED", "operator-secret-seed-should-not-print")
    monkeypatch.setenv("HERMES_FETCH_HERMES_PYTHON", "python")
    cfg = load_config(Path("examples/agentverse-mailbox-hermes.yaml"))
    cfg.hermes_mcp.mode = "fake"

    address = asyncio.run(run_bridge_for(cfg, 0.01))

    assert address == "agent1fakebridge"
    assert captured["mailbox"] is True
    assert captured["proxy"] is False


def test_run_bridge_for_propagates_child_startup_error(monkeypatch):
    from hermes_fetch_ai import uagent_app
    from hermes_fetch_ai.config import load_config

    class FakeAgent:
        address = "agent1fakebridge"

        def __init__(self, **kwargs):
            pass

        def include(self, *args, **kwargs):
            return None

    class ErrorProcess:
        exitcode = None

        def __init__(self, target=None, args=(), daemon=None):
            self.ready_conn = args[1]
            self._alive = True

        def start(self):
            self.ready_conn.send(
                {"status": "error", "error": "ImportError: google.protobuf descriptor"}
            )

        def is_alive(self):
            return self._alive

        def terminate(self):
            self._alive = False

        def join(self, timeout=None):
            return None

    monkeypatch.setattr(uagent_app, "Agent", FakeAgent)
    monkeypatch.setattr(uagent_app.multiprocessing, "Process", ErrorProcess)
    monkeypatch.setenv("UAGENT_SEED", "operator-secret-seed-should-not-print")
    monkeypatch.setenv("HERMES_FETCH_HERMES_PYTHON", "python")
    cfg = load_config(Path("examples/agentverse-mailbox-hermes.yaml"))
    cfg.hermes_mcp.mode = "fake"

    with pytest.raises(RuntimeError, match="mailbox child startup failed: ImportError"):
        asyncio.run(run_bridge_for(cfg, 0.01))


def test_run_bridge_for_fails_if_child_exits_before_window(monkeypatch):
    from hermes_fetch_ai import uagent_app
    from hermes_fetch_ai.config import load_config

    class FakeAgent:
        address = "agent1fakebridge"

        def __init__(self, **kwargs):
            pass

        def include(self, *args, **kwargs):
            return None

    class FailedProcess:
        exitcode = 1

        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            return None

        def is_alive(self):
            return False

        def terminate(self):
            return None

        def join(self, timeout=None):
            return None

    monkeypatch.setattr(uagent_app, "Agent", FakeAgent)
    monkeypatch.setattr(uagent_app.multiprocessing, "Process", FailedProcess)
    monkeypatch.setenv("UAGENT_SEED", "operator-secret-seed-should-not-print")
    monkeypatch.setenv("HERMES_FETCH_HERMES_PYTHON", "python")
    cfg = load_config(Path("examples/agentverse-mailbox-hermes.yaml"))
    cfg.hermes_mcp.mode = "fake"

    with pytest.raises(RuntimeError, match="child process exited.*exit code 1"):
        asyncio.run(run_bridge_for(cfg, 0.01))
