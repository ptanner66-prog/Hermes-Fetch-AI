"""Commands without --config use the config `setup` wrote, in the owner's config folder."""

import json
import os
from pathlib import Path

from hermes_fetch_ai import cli
from hermes_fetch_ai.audit import managed_config_path

SEED = "managed-config-test-" + "identity-material-not-a-real-seed"


def test_the_managed_config_lives_in_the_owners_config_folder(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    if os.name == "nt":
        assert managed_config_path() == tmp_path / "roaming" / "HermesFetchAI" / "bridge.yaml"
    else:
        assert managed_config_path() == tmp_path / "xdg" / "hermes-fetch-ai" / "bridge.yaml"


def test_commands_explain_that_setup_comes_first(capsys):
    assert not managed_config_path().exists()
    for command in (["serve"], ["wallet"], ["ledger"], ["seller", "credits"]):
        assert cli.main(command) == 1
        assert "run `hermes fetchai-bridge setup`" in capsys.readouterr().err


def test_doctor_checks_the_managed_config_once_there_is_one(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("UAGENT_SEED", SEED)
    assert cli.main(["doctor"]) == 0
    assert "the demo config; run `hermes fetchai-bridge setup`" in capsys.readouterr().out
    path = managed_config_path()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"payments": {"state_dir": str(tmp_path / "state")}}))
    assert cli.main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert f"config: ok: {path} (written by setup)" in out
    assert "python: " in out
    assert cli.main(["wallet"]) == 0
    assert "agent address: agent1" in capsys.readouterr().out


def test_buyer_commands_find_the_records_of_the_managed_config(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("UAGENT_SEED", SEED)
    path = managed_config_path()
    path.parent.mkdir(parents=True)
    state = tmp_path / "records"
    path.write_text(json.dumps({"payments": {"state_dir": str(state)}}))
    (state).mkdir()
    (state / "control.json").write_text("{}")
    assert cli.main(["buyer", "status"]) == 1
    # It looked in the managed config's records folder, not the default one.
    assert f"{Path(state, 'control.json')} is not a control file" in capsys.readouterr().err
