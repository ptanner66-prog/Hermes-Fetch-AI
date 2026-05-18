from hermes_fetch_ai.hermes_probe import probe


def test_probe_hermes_never_crashes_when_hermes_is_absent(monkeypatch):
    def fake_find_spec(name):
        if name.startswith("agent"):
            raise ModuleNotFoundError(name)
        return None

    monkeypatch.setattr("hermes_fetch_ai.hermes_probe.importlib.util.find_spec", fake_find_spec)
    monkeypatch.setattr("hermes_fetch_ai.hermes_probe.shutil.which", lambda name: None)
    info = probe()
    assert info["hermes_build_server"] == "not importable"
    assert info["hermes_mcp_serve_module"] == "not importable"
    assert info["hermes_mcp_serve_help"] == "not checked"
