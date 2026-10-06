"""The plugin's `install` and `setup`, and the version check between plugin and bridge."""

from __future__ import annotations

import argparse
import json
import os
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from hermes_fetch_ai import cli

from .test_hermes_directory_plugin import CurrentHermesCtx, plugin

SEED_NAME = "UAGENT_SEED"


class Ctx(CurrentHermesCtx):
    def set_config(self, key, value):
        self.settings[key] = value


def fake_bridge(tmp_path: Path, version: str = plugin.PLUGIN_VERSION, buying: bool = True) -> str:
    """A stand-in `hermes-fetch-ai` that records how it was run."""
    record = tmp_path / "bridge-runs.jsonl"
    script = tmp_path / "fake_bridge.py"
    script.write_text(
        "import json, os, sys\n"
        "if sys.argv[1:] == ['--version']:\n"
        f"    print('hermes-fetch-ai {version}'); sys.exit(0)\n"
        "names = ['UAGENT_SEED', 'AGENTVERSE_API_KEY', 'HERMES_FETCH_AI_PLUGIN_VERSION']\n"
        f"with open({str(record)!r}, 'a') as f:\n"
        "    f.write(json.dumps({'argv': sys.argv[1:], 'env': {n: os.environ.get(n) for n in names}})"
        " + '\\n')\n"
        "target = os.environ.get('HERMES_FETCH_AI_SETUP_RESULT')\n"
        "if target:\n"
        f"    json.dump({{'buying': {buying!r}, 'selling': True}}, open(target, 'w'))\n",
        encoding="utf-8",
    )
    if os.name == "nt":
        launcher = tmp_path / "bridge.cmd"
        launcher.write_text(f'@"{sys.executable}" "{script}" %*\n')
    else:
        launcher = tmp_path / "bridge"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
        launcher.chmod(0o755)
    return str(launcher)


def runs(tmp_path: Path) -> list[dict[str, Any]]:
    record = tmp_path / "bridge-runs.jsonl"
    if not record.exists():
        return []
    return [json.loads(line) for line in record.read_text().splitlines()]


@pytest.fixture
def hermes_env(monkeypatch):
    """Hermes' .env writer, as the plugin sees it while Hermes runs."""
    saved: dict[str, str] = {}
    config = types.ModuleType("hermes_cli.config")
    config.save_env_value = lambda name, value: saved.__setitem__(name, value)
    config.get_env_value = lambda name: saved.get(name)
    monkeypatch.setitem(sys.modules, "hermes_cli", types.ModuleType("hermes_cli"))
    monkeypatch.setitem(sys.modules, "hermes_cli.config", config)
    return saved


@pytest.fixture
def at_terminal(monkeypatch):
    answers: list[str] = []
    monkeypatch.setattr(plugin, "_interactive", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": answers.pop(0))
    return answers


# -- install ---------------------------------------------------------------------------


def test_install_leaves_a_matching_bridge_alone(tmp_path, capsys):
    bridge = fake_bridge(tmp_path)
    assert plugin.install_bridge([], bridge) == 0
    assert "is installed, the version this plugin needs" in capsys.readouterr().out


def test_install_needs_uv_or_pipx(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(plugin.shutil, "which", lambda name: None)
    assert plugin.install_bridge([], "") == 1
    assert plugin.UV_DOCS in capsys.readouterr().out


def test_install_runs_uv_pinned_to_the_plugins_version(tmp_path, monkeypatch, capsys):
    calls = []
    found = iter([None, "/home/owner/.local/bin/hermes-fetch-ai"])
    monkeypatch.setattr(plugin, "resolve_bridge_command", lambda configured="": next(found))
    monkeypatch.setattr(plugin.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(plugin.subprocess, "call", lambda command, env: calls.append(env) or 0)
    monkeypatch.setenv("UV_INDEX_URL", "https://pypi.example/simple")
    monkeypatch.setenv("OPENROUTER_API_" + "KEY", "provider-key-for-tests")
    assert plugin.install_bridge(["--yes"], "") == 0
    out = capsys.readouterr().out
    expected = f"uv tool install --force --python 3.12 {plugin.BRIDGE_REQUIREMENT}"
    assert f"/usr/bin/{expected}" in out and "Next: hermes fetchai-bridge setup" in out
    (env,) = calls
    assert env["UV_INDEX_URL"] == "https://pypi.example/simple"
    assert "OPENROUTER_API_" + "KEY" not in env


def test_install_asks_first_and_never_waits_when_unattended(monkeypatch, capsys, at_terminal):
    monkeypatch.setattr(plugin, "resolve_bridge_command", lambda configured="": None)
    monkeypatch.setattr(plugin.shutil, "which", lambda name: f"/usr/bin/{name}")
    ran = []
    monkeypatch.setattr(plugin.subprocess, "call", lambda command, env: ran.append(command) or 0)
    at_terminal.append("n")
    assert plugin.install_bridge([], "") == 1
    assert "Nothing was installed." in capsys.readouterr().out
    monkeypatch.setattr(plugin, "_interactive", lambda: False)
    assert plugin.install_bridge([], "") == 2
    assert "with --yes" in capsys.readouterr().out
    assert ran == []


def test_a_failed_install_says_so(monkeypatch, capsys):
    monkeypatch.setattr(plugin, "resolve_bridge_command", lambda configured="": None)
    monkeypatch.setattr(
        plugin.shutil, "which", lambda name: "/usr/bin/pipx" if name == "pipx" else None
    )
    commands = []
    monkeypatch.setattr(
        plugin.subprocess, "call", lambda command, env: commands.append(command) or 1
    )
    assert plugin.install_bridge(["--yes"], "") == 1
    assert commands[0][:2] == ["/usr/bin/pipx", "install"]
    assert "did not finish" in capsys.readouterr().out


def test_an_installed_bridge_off_the_path_is_explained(monkeypatch, capsys):
    monkeypatch.setattr(plugin, "resolve_bridge_command", lambda configured="": None)
    monkeypatch.setattr(plugin.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(plugin.subprocess, "call", lambda command, env: 0)
    assert plugin.install_bridge(["--yes"], "") == 0
    assert "uv tool update-shell" in capsys.readouterr().out
    monkeypatch.setattr(
        plugin.shutil, "which", lambda name: "/usr/bin/pipx" if name == "pipx" else None
    )
    assert plugin.install_bridge(["--yes"], "") == 0
    assert "pipx ensurepath" in capsys.readouterr().out


# -- the plugin's own secrets ---------------------------------------------------------


def test_secrets_are_kept_through_hermes(hermes_env, monkeypatch):
    monkeypatch.delenv(SEED_NAME, raising=False)
    assert plugin.save_secret(SEED_NAME, "s" * 64)
    assert hermes_env == {SEED_NAME: "s" * 64} and os.environ[SEED_NAME] == "s" * 64


def test_a_hermes_that_does_not_keep_the_secret_is_noticed(hermes_env, monkeypatch):
    config = sys.modules["hermes_cli.config"]
    monkeypatch.setattr(config, "save_env_value", lambda name, value: None)  # managed install
    assert not plugin.save_secret(SEED_NAME, "s" * 64)

    def broken(name, value):
        raise PermissionError("read-only")

    monkeypatch.setattr(config, "save_env_value", broken)
    assert not plugin.save_secret(SEED_NAME, "s" * 64)
    monkeypatch.setitem(sys.modules, "hermes_cli.config", None)
    assert not plugin.save_secret(SEED_NAME, "s" * 64)


# -- setup -----------------------------------------------------------------------------


def test_setup_makes_the_key_then_asks_the_bridges_questions(
    tmp_path, monkeypatch, hermes_env, at_terminal, capsys
):
    monkeypatch.delenv(SEED_NAME, raising=False)
    monkeypatch.delenv("AGENTVERSE_API_KEY", raising=False)
    monkeypatch.setattr(plugin.getpass, "getpass", lambda prompt: " av-key ")
    at_terminal.append("y")  # turn on the buying tools
    ctx = Ctx()
    bridge = fake_bridge(tmp_path, buying=True)
    assert plugin.setup_bridge(ctx, [], bridge) == 0
    seed = hermes_env[SEED_NAME]
    assert len(seed) == 64 and hermes_env["AGENTVERSE_API_KEY"] == "av-key"
    (run,) = runs(tmp_path)
    assert run["argv"] == ["setup"]
    assert run["env"] == {
        SEED_NAME: seed,
        "AGENTVERSE_API_KEY": "av-key",
        plugin.PLUGIN_VERSION_VAR: plugin.PLUGIN_VERSION,
    }
    assert ctx.settings["buyer_tools"] is True
    out = capsys.readouterr().out
    assert "keeping it in Hermes' .env as UAGENT_SEED" in out
    assert seed not in out


def test_setup_with_answers_asks_nothing_itself(tmp_path, monkeypatch, hermes_env, capsys):
    monkeypatch.setenv(SEED_NAME, "existing-seed-" + "x" * 40)
    monkeypatch.delenv("AGENTVERSE_API_KEY", raising=False)
    monkeypatch.setattr(plugin.getpass, "getpass", pytest.fail)
    ctx = Ctx()
    bridge = fake_bridge(tmp_path, buying=True)
    assert plugin.setup_bridge(ctx, ["--answers", "answers.json"], bridge) == 0
    assert runs(tmp_path)[0]["argv"] == ["setup", "--answers", "answers.json"]
    assert hermes_env == {}  # the existing key stays as it is
    assert "buyer_tools" not in ctx.settings
    assert 'turn on "Let Hermes buy from other agents"' in capsys.readouterr().out


def test_setup_notes_buying_tools_left_on_without_buying(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(SEED_NAME, "existing-seed-" + "x" * 40)
    ctx = Ctx(settings={"buyer_tools": True})
    assert plugin.setup_bridge(ctx, ["--answers", "-"], fake_bridge(tmp_path, buying=False)) == 0
    assert "is on, but your agent does not buy" in capsys.readouterr().out


def test_setup_stops_when_hermes_cannot_keep_the_key(tmp_path, monkeypatch, at_terminal, capsys):
    monkeypatch.delenv(SEED_NAME, raising=False)
    monkeypatch.setitem(sys.modules, "hermes_cli.config", None)
    assert plugin.setup_bridge(Ctx(), [], fake_bridge(tmp_path)) == 1
    assert "nothing was set up" in capsys.readouterr().out
    assert runs(tmp_path) == []


def test_setup_needs_a_terminal_or_answers(tmp_path, capsys):
    assert plugin.setup_bridge(Ctx(), [], fake_bridge(tmp_path)) == 2
    assert "run it in a terminal" in capsys.readouterr().out


def test_setup_offers_to_install_the_bridge_first(monkeypatch, capsys):
    monkeypatch.setattr(plugin, "resolve_bridge_command", lambda configured="": None)
    monkeypatch.setattr(plugin, "install_bridge", lambda argv, configured="": 2)
    assert plugin.setup_bridge(Ctx(), [], "") == 2
    assert "the bridge itself needs installing" in capsys.readouterr().out


def test_install_and_setup_are_the_plugins_own_commands(monkeypatch):
    seen = []
    monkeypatch.setattr(
        plugin, "install_bridge", lambda argv, configured="": seen.append(argv) or 0
    )
    monkeypatch.setattr(
        plugin, "setup_bridge", lambda ctx, argv, configured="": seen.append(argv) or 0
    )
    monkeypatch.setattr(plugin, "run_bridge", lambda argv, configured="": seen.append(argv) or 0)
    ctx = Ctx()
    plugin.register(ctx)
    command = ctx.commands["fetchai-bridge"]
    parser = argparse.ArgumentParser()
    command["setup_fn"](parser)
    for argv in (["install", "--yes"], ["setup"], ["status"]):
        command["handler_fn"](parser.parse_args(argv))
    assert seen == [["--yes"], [], ["status"]]


# -- versions ---------------------------------------------------------------------------


def test_the_bridge_says_when_it_and_the_plugin_differ(monkeypatch, capsys):
    from hermes_fetch_ai import __version__

    assert plugin.bridge_environment({})[plugin.PLUGIN_VERSION_VAR] == plugin.PLUGIN_VERSION
    assert plugin.PLUGIN_VERSION_VAR == cli.PLUGIN_VERSION_VAR
    monkeypatch.setenv(cli.PLUGIN_VERSION_VAR, "0.9.0")
    cli.main(["demo", "local"])
    assert "the fetchai-bridge plugin is 0.9.0; to match them" in capsys.readouterr().err
    monkeypatch.setenv(cli.PLUGIN_VERSION_VAR, __version__)
    cli.main(["demo", "local"])
    assert "fetchai-bridge plugin is" not in capsys.readouterr().err


def test_bridge_version_reads_what_the_bridge_says(tmp_path):
    assert plugin.bridge_version(fake_bridge(tmp_path, version="1.2.3")) == "1.2.3"
    assert plugin.bridge_version(str(tmp_path / "missing")) is None
