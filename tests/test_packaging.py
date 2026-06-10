from pathlib import Path

import pytest

from hermes_fetch_ai import cli
from hermes_fetch_ai.config import load_config


def test_packaged_default_config_stays_in_sync_with_example():
    example = Path("examples/local-direct.yaml").read_bytes()
    packaged = Path("src/hermes_fetch_ai/data/local-direct.yaml").read_bytes()
    assert packaged == example


def test_default_config_path_resolves_and_loads():
    path = cli.default_config_path()
    assert path.is_file()
    cfg = load_config(path)
    assert cfg.policy.public_tools == ["echo"]


def test_default_config_falls_back_to_packaged_data(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "ROOT", tmp_path / "not-a-repo")
    path = cli.default_config_path()
    assert path.is_file()
    assert path.name == "local-direct.yaml"
    assert "data" in path.parts


def test_default_config_error_is_actionable(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "ROOT", tmp_path / "not-a-repo")

    class NoFile:
        def joinpath(self, *_):
            return tmp_path / "missing.yaml"

    monkeypatch.setattr(cli.resources, "files", lambda _: NoFile())
    with pytest.raises(FileNotFoundError, match="--config"):
        cli.default_config_path()
