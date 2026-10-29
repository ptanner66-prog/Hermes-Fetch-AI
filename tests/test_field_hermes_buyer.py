"""Field test: the plugin's buying guards against a real hermes-agent install.

Skipped unless both env vars are set (see tests/test_field_hermes_stdio.py):

  HERMES_FETCH_FIELD_TEST=1
  HERMES_FETCH_HERMES_PYTHON=/path/to/hermes-venv/bin/python

The plugin uses three of Hermes' own functions: whether YOLO mode is on
(`tools.approval.is_approval_bypass_active`), the confirmation prompt
(`tools.approval_prompt.request_elicitation_consent`), and the .env writer
setup keeps the agent's key with (`hermes_cli.config.save_env_value`). This
loads the plugin inside Hermes' Python and checks each still behaves as the
plugin relies on: YOLO is seen however it was turned on, the prompt declines
when nobody can answer, and the key lands in Hermes' .env. CI runs it
against Hermes 0.21.5 and a pinned main; it is the canary for a Hermes
change that would break the payment approval or setup.
"""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("HERMES_FETCH_FIELD_TEST") != "1"
    or not os.environ.get("HERMES_FETCH_HERMES_PYTHON"),
    reason="field test requires HERMES_FETCH_FIELD_TEST=1 and HERMES_FETCH_HERMES_PYTHON",
)

PLUGIN = Path(__file__).resolve().parents[1] / "hermes-plugin" / "fetchai-bridge" / "__init__.py"
PROBE = textwrap.dedent(
    """
    import importlib.util, json, sys
    spec = importlib.util.spec_from_file_location("fetchai_bridge_plugin", sys.argv[1])
    plugin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin)
    out = {"yolo": plugin.yolo_active()}
    if sys.argv[2:] == ["ask"]:
        out["consent"] = plugin.ask_owner("Pay 0.05 testnet FET to another agent?", "field test")
        # Hermes' prompt itself: a prompt that raised would also read as "decline" above.
        import inspect
        from tools.approval_prompt import request_elicitation_consent as prompt
        out["parameters"] = sorted(inspect.signature(prompt).parameters)
        try:
            out["prompt"] = prompt("Pay 0.05 testnet FET?", "field test", title="Pay another agent?")
        except Exception as exc:
            out["prompt"] = "raised " + type(exc).__name__
    if sys.argv[2:] == ["save"]:
        out["saved"] = plugin.save_secret("UAGENT_SEED", "f" * 64)
    print(json.dumps(out))
    """
)


def probe(tmp_path, *, ask=False, save=False, settings="", **env):
    home = tmp_path / "hermes-home"
    home.mkdir(exist_ok=True)
    (home / "config.yaml").write_text(settings)
    script = tmp_path / "probe.py"
    script.write_text(PROBE)
    base = {"PATH": os.environ.get("PATH", ""), "HOME": str(home), "HERMES_HOME": str(home)}
    if sys.platform == "win32":
        base["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", "")
    done = subprocess.run(
        [
            os.environ["HERMES_FETCH_HERMES_PYTHON"],
            str(script),
            str(PLUGIN),
            *(["ask"] if ask else []),
            *(["save"] if save else []),
        ],
        env={**base, **env},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=tmp_path,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_the_plugin_sees_yolo_mode_however_it_is_turned_on(tmp_path):
    assert probe(tmp_path) == {"yolo": False}
    assert probe(tmp_path, HERMES_YOLO_MODE="1") == {"yolo": True}
    assert probe(tmp_path, settings='approvals:\n  mode: "off"\n') == {"yolo": True}


def test_the_payment_prompt_declines_when_nobody_can_answer(tmp_path):
    # A one-shot run (`hermes chat -q`), and a process with no session or terminal.
    for result in (
        probe(tmp_path, ask=True, HERMES_SINGLE_QUERY_SESSION="1"),
        probe(tmp_path, ask=True),
    ):
        assert result["consent"] == "decline"
        # It declined because nobody can answer, not because the prompt broke or changed.
        assert result["prompt"] == "decline"
        assert {"message", "description", "title"} <= set(result["parameters"])


def test_setup_keeps_the_agents_key_in_hermes_env(tmp_path):
    # `hermes fetchai-bridge setup` stores UAGENT_SEED with Hermes' own .env writer.
    assert probe(tmp_path, save=True)["saved"] is True
    env_file = tmp_path / "hermes-home" / ".env"
    assert "UAGENT_SEED=" + "f" * 64 in env_file.read_text()
    if sys.platform != "win32":
        assert oct(env_file.stat().st_mode & 0o777) == "0o600"
