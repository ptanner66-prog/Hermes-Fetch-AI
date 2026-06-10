import importlib.util

from hermes_fetch_ai.hermes_probe import probe


def test_probe_reports_not_importable_when_hermes_absent(monkeypatch):
    def raising_find_spec(name, *args, **kwargs):
        raise ModuleNotFoundError("No module named 'agent'")

    monkeypatch.setattr(importlib.util, "find_spec", raising_find_spec)
    info = probe()
    assert info["hermes_build_server"] == "not importable"
    assert info["fake_mode"] == "ok"


def test_probe_returns_actionable_fields():
    info = probe()
    for key in ("fake_mode", "uagents", "mcp", "hermes_console", "hermes_build_server"):
        assert key in info
    assert info["fake_tools"] == 2
