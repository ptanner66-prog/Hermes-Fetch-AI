"""The fetchai-bridge Hermes directory plugin (hermes-plugin/fetchai-bridge).

The plugin is stdlib-only, so these tests drive its register() with fake Hermes
contexts. CI's hermes-plugin job runs the real `hermes plugins validate` and
`hermes plugins doctor` checks against a pinned hermes-agent.
"""

import argparse
import ast
import importlib.util
import json
import os
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

import yaml

from hermes_fetch_ai import config as bridge_config

PLUGIN_DIR = Path("hermes-plugin/fetchai-bridge")
CATALOG_ENTRY = Path("upstream/hermes-pr/plugin-catalog/fetchai-bridge.yaml")
STDLIB_IMPORTS = {
    "__future__",
    "argparse",
    "collections",
    "os",
    "pathlib",
    "shutil",
    "subprocess",
    "sys",
    "typing",
}


def _load_plugin():
    spec = importlib.util.spec_from_file_location(
        "fetchai_bridge_plugin", PLUGIN_DIR / "__init__.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plugin = _load_plugin()


class OlderHermesCtx:
    """A plugin context without settings or plugin-skill support."""

    def __init__(self):
        self.commands = {}

    def register_cli_command(self, name, help, setup_fn, handler_fn=None, description=""):
        self.commands[name] = {"setup_fn": setup_fn, "handler_fn": handler_fn}


class CurrentHermesCtx(OlderHermesCtx):
    def __init__(self, settings=None):
        super().__init__()
        self.skills = {}
        self.settings = settings or {}

    def register_skill(self, name, path, description="", frontmatter=None):
        self.skills[name] = Path(path)

    def get_config(self, key, default=None):
        return self.settings.get(key, default)


def _frontmatter(path: Path) -> dict[str, Any]:
    match = re.match(r"^---\n(.*?)\n---\n", path.read_text(encoding="utf-8"), re.DOTALL)
    assert match, f"{path} must start with YAML frontmatter"
    meta: dict[str, Any] = yaml.safe_load(match.group(1))
    return meta


def test_manifest_is_catalog_ready():
    manifest = yaml.safe_load((PLUGIN_DIR / "plugin.yaml").read_text(encoding="utf-8"))
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert manifest["name"] == PLUGIN_DIR.name == plugin.PLUGIN_NAME
    assert manifest["description"]
    assert manifest["version"] == project["version"]
    assert manifest["requires_hermes"].startswith(">=")
    # The bridge's pinned dependencies must never be installed into Hermes' environment.
    assert manifest["python_runtime"] == "external"
    assert "python_dependencies" not in manifest
    assert not (PLUGIN_DIR / "pyproject.toml").exists()
    seed = manifest["config_schema"]["uagent_seed"]
    assert seed["type"] == "secret" and seed["env"] == "UAGENT_SEED"


def test_catalog_entry_draft_matches_the_plugin():
    entry = yaml.safe_load(CATALOG_ENTRY.read_text(encoding="utf-8"))
    manifest = yaml.safe_load((PLUGIN_DIR / "plugin.yaml").read_text(encoding="utf-8"))
    assert entry["name"] == manifest["name"]
    assert entry["repo"] == manifest["homepage"]
    assert entry["subdir"] == PLUGIN_DIR.as_posix()
    assert entry["version"] == manifest["version"]
    assert entry["requires_hermes"] == manifest["requires_hermes"]
    # Catalog rule 6: declared capabilities must match what register() adds.
    assert entry["capabilities"] == {
        "provides_tools": [],
        "provides_hooks": [],
        "provides_middleware": [],
        "requires_env": [],
    }


def test_plugin_imports_only_the_standard_library():
    tree = ast.parse((PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported <= STDLIB_IMPORTS


def test_register_wires_cli_command_and_bundled_skill():
    ctx = CurrentHermesCtx()
    plugin.register(ctx)
    assert set(ctx.commands) == {"fetchai-bridge"}
    assert set(ctx.skills) == {"operate"}
    skill = ctx.skills["operate"]
    assert skill.is_file()
    meta = _frontmatter(skill)
    assert meta["name"] == "operate"
    assert len(meta["description"]) <= 60 and meta["description"].endswith(".")


def test_register_works_on_hermes_without_plugin_skills_or_settings():
    ctx = OlderHermesCtx()
    plugin.register(ctx)
    assert set(ctx.commands) == {"fetchai-bridge"}


def test_cli_arguments_pass_through_unchanged(monkeypatch):
    seen = []
    monkeypatch.setattr(
        plugin, "run_bridge", lambda argv, configured="": seen.append((argv, configured)) or 7
    )
    ctx = CurrentHermesCtx(settings={"command": "/opt/bridge/bin/hermes-fetch-ai"})
    plugin.register(ctx)
    command = ctx.commands["fetchai-bridge"]
    parser = argparse.ArgumentParser(prog="hermes fetchai-bridge")
    command["setup_fn"](parser)

    args = parser.parse_args(["serve", "--config", "bridge.yaml"])
    assert command["handler_fn"](args) == 7
    args = parser.parse_args(["doctor", "--help"])
    command["handler_fn"](args)
    command["handler_fn"](parser.parse_args([]))
    assert seen == [
        (["serve", "--config", "bridge.yaml"], "/opt/bridge/bin/hermes-fetch-ai"),
        (["doctor", "--help"], "/opt/bridge/bin/hermes-fetch-ai"),
        (["--help"], "/opt/bridge/bin/hermes-fetch-ai"),
    ]


def test_run_bridge_returns_exit_code_and_hands_over_a_clean_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(["/hermes/checkout", "/hermes/site"]))
    monkeypatch.setenv("VIRTUAL_ENV", "/hermes/venv")
    monkeypatch.setenv("UAGENT_SEED", "seed-for-tests-" + "0123456789abcdef0123456789")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    # Hermes loads provider keys from its .env; the bridge must not get them.
    monkeypatch.setenv("OPENROUTER_API_" + "KEY", "provider-key-for-tests")
    seen_file = tmp_path / "seen.json"
    names = [
        "PYTHONPATH",
        "VIRTUAL_ENV",
        "UAGENT_SEED",
        "HERMES_HOME",
        "OPENROUTER_API_" + "KEY",
        plugin.HERMES_PYTHON_VAR,
        plugin.HERMES_PYTHONPATH_VAR,
    ]
    code = (
        "import json, os, sys\n"
        f"seen = {{'argv': sys.argv[1:], 'env': {{k: os.environ.get(k) for k in {names!r}}}}}\n"
        f"json.dump(seen, open({str(seen_file)!r}, 'w'))\n"
        "sys.exit(3)\n"
    )
    # Use this Python as the "bridge" executable so the check runs on every OS.
    assert plugin.run_bridge(["-c", code, "doctor", "--flag"], configured=sys.executable) == 3
    seen = json.loads(seen_file.read_text())
    assert seen["argv"] == ["doctor", "--flag"]
    env = seen["env"]
    assert env["PYTHONPATH"] is None and env["VIRTUAL_ENV"] is None
    assert env["OPENROUTER_API_" + "KEY"] is None
    assert env["UAGENT_SEED"] == "seed-for-tests-" + "0123456789abcdef0123456789"
    assert env["HERMES_HOME"] == str(tmp_path / "hermes-home")
    assert env[plugin.HERMES_PYTHON_VAR] == sys.executable
    assert env[plugin.HERMES_PYTHONPATH_VAR].startswith("/hermes/checkout")


def test_missing_bridge_explains_how_to_install(capsys, tmp_path):
    missing = str(tmp_path / "nowhere" / "hermes-fetch-ai")
    assert plugin.run_bridge(["doctor"], configured=missing) == 1
    err = capsys.readouterr().err
    assert plugin.INSTALL_HINT in err
    assert "plugins.entries.fetchai-bridge.settings.command" in err


def test_handover_variable_names_match_the_bridge():
    assert plugin.HERMES_PYTHON_VAR == bridge_config.HERMES_PYTHON_VAR
    assert plugin.HERMES_PYTHONPATH_VAR == bridge_config.HERMES_PYTHONPATH_VAR
