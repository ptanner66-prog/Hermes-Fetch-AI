import sys

from hermes_fetch_ai.config import HERMES_PYTHON_VAR, HERMES_PYTHONPATH_VAR
from hermes_fetch_ai.hermes_probe import probe


def test_probe_without_hermes_reports_not_importable(monkeypatch):
    monkeypatch.delenv(HERMES_PYTHON_VAR, raising=False)
    info = probe()
    assert info["hermes_tools_server"] == "not importable"
    assert info["hermes_python"].startswith("not handed over")
    assert info["fake_tools"] == 2


def test_probe_checks_the_interpreter_the_plugin_hands_over(monkeypatch, tmp_path):
    # A stand-in for Hermes: any interpreter that can import the tools server module.
    module_dir = tmp_path / "agent" / "transports"
    module_dir.mkdir(parents=True)
    for package in (tmp_path / "agent", module_dir):
        (package / "__init__.py").write_text("", encoding="utf-8")
    (module_dir / "hermes_tools_mcp_server.py").write_text("", encoding="utf-8")
    monkeypatch.setenv(HERMES_PYTHON_VAR, sys.executable)
    monkeypatch.setenv(HERMES_PYTHONPATH_VAR, str(tmp_path))
    info = probe()
    assert info["hermes_python"] == sys.executable
    assert info["hermes_tools_server"] == "importable"

    monkeypatch.delenv(HERMES_PYTHONPATH_VAR)
    assert probe()["hermes_tools_server"] == "not importable"
