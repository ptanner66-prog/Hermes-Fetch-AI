import argparse
import ast
import importlib.metadata
from pathlib import Path

from hermes_fetch_ai import hermes_plugin


class FakeCtx:
    def __init__(self):
        self.commands = {}

    def register_cli_command(self, name, help, setup_fn, handler_fn=None, description=""):
        self.commands[name] = {
            "help": help,
            "setup_fn": setup_fn,
            "handler_fn": handler_fn,
            "description": description,
        }


def _parse(argv):
    parser = argparse.ArgumentParser(prog="hermes")
    sub = parser.add_subparsers(dest="cmd")
    fetchai = sub.add_parser("fetchai")
    hermes_plugin._setup_parser(fetchai)
    return parser.parse_args(argv)


def test_register_wires_fetchai_cli_command():
    ctx = FakeCtx()
    hermes_plugin.register(ctx)
    assert "fetchai" in ctx.commands
    cmd = ctx.commands["fetchai"]
    assert callable(cmd["setup_fn"]) and callable(cmd["handler_fn"])
    assert "Fetch.ai" in cmd["help"]


def test_entry_point_declared_and_loads_register():
    eps = importlib.metadata.entry_points()
    group = eps.select(group="hermes_agent.plugins")
    names = {ep.name: ep for ep in group}
    assert "fetchai" in names
    module = names["fetchai"].load()
    assert callable(module.register)


def test_handler_maps_demo_to_bridge_cli(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "hermes_fetch_ai.cli.main", lambda argv=None: seen.update(argv=argv) or 0
    )
    args = _parse(["fetchai", "demo", "local"])
    assert hermes_plugin._handle(args) == 0
    assert seen["argv"] == ["demo", "local"]


def test_handler_maps_doctor_flags(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "hermes_fetch_ai.cli.main", lambda argv=None: seen.update(argv=argv) or 0
    )
    args = _parse(["fetchai", "doctor", "--config", "x.yaml", "--contamination-scan"])
    assert hermes_plugin._handle(args) == 0
    assert seen["argv"] == ["doctor", "--config", "x.yaml", "--contamination-scan"]


def test_handler_maps_serve_and_probe(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "hermes_fetch_ai.cli.main", lambda argv=None: calls.append(argv) or 0
    )
    hermes_plugin._handle(_parse(["fetchai", "serve", "--config", "c.yaml"]))
    hermes_plugin._handle(_parse(["fetchai", "probe"]))
    assert calls == [["serve", "--config", "c.yaml"], ["probe-hermes"]]


def test_plugin_module_has_no_heavy_top_level_imports():
    src = Path(hermes_plugin.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    top_level = [
        n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))
    ]
    imported = set()
    for node in top_level:
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        else:
            imported.add((node.module or "").split(".")[0])
    assert imported <= {"__future__", "typing"}
