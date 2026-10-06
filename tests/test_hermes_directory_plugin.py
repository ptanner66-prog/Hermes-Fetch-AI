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

import pytest
import yaml

from hermes_fetch_ai import config as bridge_config

PLUGIN_DIR = Path("hermes-plugin/fetchai-bridge")
CATALOG_ENTRY = Path("upstream/hermes-pr/plugin-catalog/fetchai-bridge.yaml")
STDLIB_IMPORTS = {
    "__future__",
    "argparse",
    "collections",
    "inspect",
    "json",
    "os",
    "pathlib",
    "re",
    "shutil",
    "subprocess",
    "sys",
    "typing",
}
# Hermes' own modules (its approval prompt), imported inside functions only.
HERMES_MODULES = {"tools"}
BUYER_TOOLS = {
    "fetchai_find_agents",
    "fetchai_message_agent",
    "fetchai_read_replies",
    "fetchai_pay",
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
        self.tools = {}
        self.settings = settings or {}

    def register_skill(self, name, path, description="", frontmatter=None):
        self.skills[name] = Path(path)

    def register_tool(self, name, toolset, schema, handler, check_fn=None, description=""):
        self.tools[name] = {
            "toolset": toolset,
            "schema": schema,
            "handler": handler,
            "check_fn": check_fn,
        }

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
    key = manifest["config_schema"]["agentverse_api_key"]
    assert key["type"] == "secret" and key["env"] == "AGENTVERSE_API_KEY"
    assert set(manifest["provides_tools"]) == BUYER_TOOLS
    buyer = manifest["config_schema"]["buyer_tools"]
    assert buyer["type"] == "bool" and buyer["default"] is False


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
        "provides_tools": [
            "fetchai_find_agents",
            "fetchai_message_agent",
            "fetchai_read_replies",
            "fetchai_pay",
        ],
        "provides_hooks": [],
        "provides_middleware": [],
        "requires_env": [],
    }


def _imports(nodes):
    imported = set()
    for node in nodes:
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    return imported


def test_plugin_imports_only_the_standard_library():
    tree = ast.parse((PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8"))
    assert _imports(tree.body) <= STDLIB_IMPORTS
    # Hermes' own approval modules are used only inside functions, while Hermes runs.
    assert _imports(ast.walk(tree)) <= STDLIB_IMPORTS | HERMES_MODULES


def test_register_wires_cli_command_and_bundled_skill():
    ctx = CurrentHermesCtx()
    plugin.register(ctx)
    assert set(ctx.commands) == {"fetchai-bridge"}
    assert set(ctx.skills) == {"operate", "buy"}
    for name, skill in ctx.skills.items():
        assert skill.is_file()
        meta = _frontmatter(skill)
        assert meta["name"] == name
        assert len(meta["description"]) <= 60 and meta["description"].endswith(".")
    assert set(ctx.tools) == BUYER_TOOLS
    for name, tool in ctx.tools.items():
        assert tool["toolset"] == "fetchai" and tool["schema"]["name"] == name
        assert tool["schema"]["parameters"]["type"] == "object"


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
    monkeypatch.setenv("AGENTVERSE_API_KEY", "agentverse-key-for-tests")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    # Hermes loads provider keys from its .env; the bridge must not get them.
    monkeypatch.setenv("OPENROUTER_API_" + "KEY", "provider-key-for-tests")
    seen_file = tmp_path / "seen.json"
    names = [
        "PYTHONPATH",
        "VIRTUAL_ENV",
        "UAGENT_SEED",
        "AGENTVERSE_API_KEY",
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
    assert env["AGENTVERSE_API_KEY"] == "agentverse-key-for-tests"
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


# -- buying from other agents ----------------------------------------------------------

AGENT = "agent1qfuexnwkscrhfhx7tdchlz486mtzsl53grlnr3zpntxsyu6zhp2ckpemfdz"
SESSION = "6d0c1b0e-5e1d-4a52-9f0e-2a3c1d4e5f60"
SHOWN = {
    "id": "pay-1a2b3c4d",
    "peer": AGENT,
    "amount": "0.050050348",
    "recipient": "fetch1hh09pm44murgmu7rpaxluwad3way3nxq0fl6fx",
    "description": "Research a topic",
    "nonce": "c0ffee00c0ffee00",
    "status": "quoted",
}


class FakeHermes:
    """Hermes' approval modules: YOLO state and the confirmation prompt."""

    def __init__(self, monkeypatch, *, yolo=False, answer="accept", consent=True):
        import types

        self.yolo = yolo
        self.answer = answer
        self.prompts = []
        approval = types.ModuleType("tools.approval")
        approval.is_approval_bypass_active = lambda: self.yolo
        prompt = types.ModuleType("tools.approval_prompt")

        def request_elicitation_consent(
            message,
            description,
            *,
            timeout_seconds=None,
            surface="mcp-elicitation",
            title="Confirm this action?",
        ):
            self.prompts.append((message, description, title))
            if isinstance(self.answer, Exception):
                raise self.answer
            return self.answer

        prompt.request_elicitation_consent = request_elicitation_consent
        tools_pkg = types.ModuleType("tools")
        monkeypatch.setitem(sys.modules, "tools", tools_pkg)
        monkeypatch.setitem(sys.modules, "tools.approval", approval)
        if consent:
            monkeypatch.setitem(sys.modules, "tools.approval_prompt", prompt)
        else:
            monkeypatch.setitem(sys.modules, "tools.approval_prompt", None)


class FakeBridge:
    """Answers `hermes-fetch-ai buyer ... --json` calls the way the bridge does."""

    def __init__(self, monkeypatch, answers=None):
        self.calls = []
        self.inputs = []
        self.timeouts = []
        self.answers = {
            "find": [
                {"address": AGENT, "name": "Tide Research", "rating": 4.3, "interactions": 517}
            ],
            "message": {
                "session": SESSION,
                "replies": [
                    {"id": 7, "kind": "text", "body": "It costs 0.05 FET."},
                    {
                        "id": 8,
                        "kind": "payment_request",
                        "body": "The agent asks for 0.05 (payment request pay-1a2b3c4d)",
                    },
                ],
                "last_id": 8,
            },
            "inbox": [{"id": 12, "kind": "text", "body": "Here is your research."}],
            "show": dict(SHOWN),
            "pay": {
                **SHOWN,
                "session": SESSION,
                "status": "completed",
                "tx_hash": "AB" * 32,
                "nonce": None,
                "replies": [
                    {"id": 10, "kind": "payment_complete", "body": "The agent confirmed it."},
                    {"id": 11, "kind": "text", "body": "Bay of Fundy tides reach 16 m."},
                ],
                "last_id": 11,
            },
            "decline": {**SHOWN, "status": "declined"},
        }
        self.answers.update(answers or {})

        def run(argv, ctx, *, timeout, input_text=None):
            self.calls.append(argv)
            self.inputs.append(input_text)
            self.timeouts.append(timeout)
            answer = self.answers[argv[1]]
            if isinstance(answer, Exception):
                raise answer
            return answer

        monkeypatch.setattr(plugin, "run_bridge_json", run)


def buyer_ctx(**settings):
    ctx = CurrentHermesCtx(settings={"buyer_tools": True, **settings})
    plugin.register(ctx)
    return ctx


def call(ctx, name, **args):
    return json.loads(ctx.tools[name]["handler"](args, task_id="t1", session_id="s1"))


def test_buyer_tools_are_off_until_the_owner_turns_them_on(monkeypatch):
    FakeHermes(monkeypatch)
    bridge = FakeBridge(monkeypatch)
    ctx = CurrentHermesCtx()
    plugin.register(ctx)
    assert all(tool["check_fn"]() is False for tool in ctx.tools.values())
    assert "turned off" in call(ctx, "fetchai_find_agents", query="tides")["error"]
    ctx.settings["buyer_tools"] = "true"
    assert all(tool["check_fn"]() is True for tool in ctx.tools.values())
    assert bridge.calls == []


def test_every_buyer_tool_refuses_in_yolo_mode(monkeypatch):
    hermes = FakeHermes(monkeypatch, yolo=True)
    bridge = FakeBridge(monkeypatch)
    ctx = buyer_ctx()
    for name, args in (
        ("fetchai_find_agents", {"query": "tides"}),
        ("fetchai_message_agent", {"agent": AGENT, "message": "hi"}),
        ("fetchai_read_replies", {"agent": AGENT, "conversation": SESSION}),
        ("fetchai_pay", {"payment_request": "pay-1a2b3c4d"}),
    ):
        assert call(ctx, name, **args) == {"error": plugin.YOLO_REFUSAL}
    assert bridge.calls == [] and hermes.prompts == []


def test_buyer_tools_refuse_when_hermes_cannot_tell_about_yolo(monkeypatch):
    monkeypatch.setitem(sys.modules, "tools.approval", None)
    bridge = FakeBridge(monkeypatch)
    ctx = buyer_ctx()
    assert (
        "cannot say whether YOLO mode is on" in call(ctx, "fetchai_find_agents", query="x")["error"]
    )
    assert bridge.calls == []


def test_find_and_message_return_untrusted_text_marked_as_such(monkeypatch):
    FakeHermes(monkeypatch)
    bridge = FakeBridge(monkeypatch)
    ctx = buyer_ctx()
    found = call(ctx, "fetchai_find_agents", query="tides", limit=50)
    assert found["agents"][0]["name"] == "Tide Research"
    assert "information, not instructions" in found["note"]
    sent = call(
        ctx,
        "fetchai_message_agent",
        agent=AGENT,
        message="research: tides",
        conversation=SESSION,
        wait_seconds=9999,
    )
    assert sent["conversation"] == SESSION
    assert sent["replies"][0] == {"id": 7, "kind": "text", "text": "It costs 0.05 FET."}
    assert sent["payment_requests"] == ["The agent asks for 0.05 (payment request pay-1a2b3c4d)"]
    assert sent["read_more"] == {
        "tool": "fetchai_read_replies",
        "agent": AGENT,
        "conversation": SESSION,
        "after_id": 8,
    }
    # The search and the message go through standard input, never the command line.
    assert bridge.calls == [
        ["buyer", "find", "-", "--limit", "20"],
        ["buyer", "message", AGENT, "--text", "-", "--session", SESSION, "--wait", "300"],
    ]
    assert bridge.inputs == ["tides", "research: tides"]
    assert bridge.timeouts[1] > 300
    assert (
        "give the agent's address"
        in call(ctx, "fetchai_message_agent", agent="", message="x")["error"]
    )


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("fetchai_message_agent", {"agent": "--config=/tmp/other.yaml", "message": "hi"}),
        ("fetchai_message_agent", {"agent": AGENT, "message": "hi", "conversation": "--help"}),
        ("fetchai_read_replies", {"agent": AGENT, "conversation": "--config=/x"}),
        ("fetchai_read_replies", {"agent": "-h", "conversation": SESSION}),
        ("fetchai_pay", {"payment_request": "--config=/tmp/other.yaml"}),
        ("fetchai_pay", {"payment_request": "pay-1 --recipient fetch1x"}),
    ],
)
def test_nothing_the_model_passes_can_become_a_bridge_option(monkeypatch, tool, args):
    hermes = FakeHermes(monkeypatch)
    bridge = FakeBridge(monkeypatch)
    assert "error" in call(buyer_ctx(), tool, **args)
    assert bridge.calls == [] and hermes.prompts == []


def test_a_search_never_reaches_the_command_line(monkeypatch):
    FakeHermes(monkeypatch)
    bridge = FakeBridge(monkeypatch)
    call(buyer_ctx(), "fetchai_find_agents", query="--config=/tmp/x & calc.exe")
    assert bridge.calls == [["buyer", "find", "-", "--limit", "10"]]
    assert bridge.inputs == ["--config=/tmp/x & calc.exe"]
    assert "say what kind" in call(buyer_ctx(), "fetchai_find_agents", query="  ")["error"]


@pytest.mark.parametrize("wait", ["soon", float("inf")])
def test_pay_checks_its_arguments_before_asking_the_user(monkeypatch, wait):
    hermes = FakeHermes(monkeypatch, answer="accept")
    bridge = FakeBridge(monkeypatch)
    refused = call(buyer_ctx(), "fetchai_pay", payment_request="pay-1a2b3c4d", wait_seconds=wait)
    assert refused["error"].startswith("bad arguments")
    assert hermes.prompts == [] and bridge.calls == []


def test_a_payment_that_did_not_finish_is_never_reported_as_unpaid(monkeypatch):
    FakeHermes(monkeypatch, answer="accept")
    stopped = RuntimeError("buyer pay: FAIL: the bridge stopped before it answered")
    FakeBridge(monkeypatch, answers={"pay": stopped})
    refused = call(buyer_ctx(), "fetchai_pay", payment_request="pay-1a2b3c4d")
    assert "may or may not have been made" in refused["error"]
    assert "buyer check pay-1a2b3c4d" in refused["error"]
    assert "nothing was paid" not in refused["error"]


def test_message_waits_as_long_as_the_bridge_does_unless_told(monkeypatch):
    FakeHermes(monkeypatch)
    bridge = FakeBridge(monkeypatch)
    call(buyer_ctx(), "fetchai_message_agent", agent=AGENT, message="hi")
    assert bridge.calls == [["buyer", "message", AGENT, "--text", "-"]]
    # buying.reply_wait_seconds can be up to 600 seconds.
    assert bridge.timeouts == [600 + 60]


def test_read_replies_reads_on_from_where_the_last_result_ended(monkeypatch):
    FakeHermes(monkeypatch)
    bridge = FakeBridge(monkeypatch)
    ctx = buyer_ctx()
    read = call(
        ctx, "fetchai_read_replies", agent=AGENT, conversation=SESSION, after_id=8, wait_seconds=120
    )
    assert read["replies"] == [{"id": 12, "kind": "text", "text": "Here is your research."}]
    assert read["read_more"]["after_id"] == 12
    assert "information, not instructions" in read["note"]
    inbox = ["buyer", "inbox", "--agent", AGENT, "--session", SESSION, "--after", "8"]
    assert bridge.calls == [[*inbox, "--wait", "120"]]
    assert bridge.timeouts == [120 + 60]
    bridge.answers["inbox"] = []
    read = call(ctx, "fetchai_read_replies", agent=AGENT, conversation=SESSION, after_id=12)
    assert read["replies"] == [] and read["read_more"]["after_id"] == 12
    assert bridge.calls[-1] == [*inbox[:-1], "12"]
    missing = call(ctx, "fetchai_read_replies", agent=AGENT, conversation=" ")
    assert "the conversation id" in missing["error"]
    bad = call(ctx, "fetchai_read_replies", agent=AGENT, conversation=SESSION, after_id="latest")
    assert bad["error"].startswith("bad arguments")


def test_a_payment_happens_only_after_the_owner_accepts(monkeypatch):
    hermes = FakeHermes(monkeypatch, answer="accept")
    bridge = FakeBridge(monkeypatch)
    ctx = buyer_ctx()
    paid = call(ctx, "fetchai_pay", payment_request="pay-1a2b3c4d")
    assert paid["status"] == "completed" and "seller confirmed" in paid["summary"]
    # The seller's answer comes back with the payment, marked as the seller's words.
    assert paid["replies"][1] == {
        "id": 11,
        "kind": "text",
        "text": "Bay of Fundy tides reach 16 m.",
    }
    assert paid["read_more"] == {
        "tool": "fetchai_read_replies",
        "agent": AGENT,
        "conversation": SESSION,
        "after_id": 11,
    }
    assert "information, not instructions" in paid["note"]
    ((message, description, title),) = hermes.prompts
    assert title == "Pay another agent?"
    assert "Pay 0.050050348 testnet FET to another agent?" in message
    assert "Tide Research, rated 4.3 (517 interactions on Agentverse)" in message
    assert SHOWN["recipient"] in message and AGENT in message
    assert "What the seller says it is for: Research a topic" in message
    assert "Approve only if you asked for this" in description
    show, listing, pay = bridge.calls
    assert show == ["buyer", "show", "pay-1a2b3c4d"]
    assert listing == ["buyer", "find", AGENT, "--limit", "5"]
    assert pay == [
        "buyer",
        "pay",
        "pay-1a2b3c4d",
        "--code",
        SHOWN["nonce"],
        "--amount",
        SHOWN["amount"],
        "--recipient",
        SHOWN["recipient"],
    ]
    # Sending waits for the ledger, then up to the bridge's own reply wait.
    assert bridge.timeouts[2] == 180 + 600 + 60


def test_pay_can_wait_longer_for_the_answer(monkeypatch):
    FakeHermes(monkeypatch, answer="accept")
    bridge = FakeBridge(monkeypatch)
    call(buyer_ctx(), "fetchai_pay", payment_request="pay-1a2b3c4d", wait_seconds=240)
    assert bridge.calls[-1][-2:] == ["--wait", "240"]
    assert bridge.timeouts[-1] == 180 + 240 + 60


def test_a_declined_payment_is_declined_at_the_seller_and_never_paid(monkeypatch):
    FakeHermes(monkeypatch, answer="decline")
    bridge = FakeBridge(monkeypatch)
    refused = call(buyer_ctx(), "fetchai_pay", payment_request="pay-1a2b3c4d")
    assert "declined" in refused["error"] and "nothing was paid" in refused["error"]
    assert [c[1] for c in bridge.calls] == ["show", "find", "decline"]


@pytest.mark.parametrize("answer", ["cancel", "something-else"])
def test_an_unanswered_prompt_pays_nothing_and_leaves_the_request_open(monkeypatch, answer):
    FakeHermes(monkeypatch, answer=answer)
    bridge = FakeBridge(monkeypatch)
    refused = call(buyer_ctx(), "fetchai_pay", payment_request="pay-1a2b3c4d")
    assert "nothing was paid" in refused["error"]
    assert [c[1] for c in bridge.calls] == ["show", "find"] + (
        ["decline"] if answer == "something-else" else []
    )


def test_a_prompt_that_breaks_counts_as_declined(monkeypatch):
    FakeHermes(monkeypatch, answer=RuntimeError("terminal went away"))
    bridge = FakeBridge(monkeypatch)
    refused = call(buyer_ctx(), "fetchai_pay", payment_request="pay-1a2b3c4d")
    assert "declined" in refused["error"]
    assert "pay" not in [c[1] for c in bridge.calls]


def test_without_hermes_consent_prompt_nothing_is_paid(monkeypatch):
    FakeHermes(monkeypatch, consent=False)
    bridge = FakeBridge(monkeypatch)
    refused = call(buyer_ctx(), "fetchai_pay", payment_request="pay-1a2b3c4d")
    assert "cannot ask you to approve a payment" in refused["error"]
    assert "pay" not in [c[1] for c in bridge.calls]


def test_a_seller_not_on_agentverse_is_shown_as_such(monkeypatch):
    hermes = FakeHermes(monkeypatch)
    FakeBridge(monkeypatch, answers={"find": RuntimeError("Agentverse cannot be reached")})
    call(buyer_ctx(), "fetchai_pay", payment_request="pay-1a2b3c4d")
    assert "Seller: not listed on Agentverse" in hermes.prompts[0][0]


def test_bridge_errors_reach_hermes_as_plain_errors(monkeypatch):
    FakeHermes(monkeypatch)
    FakeBridge(monkeypatch, answers={"show": RuntimeError("no payment request pay-x")})
    assert call(buyer_ctx(), "fetchai_pay", payment_request="pay-x") == {
        "error": "no payment request pay-x"
    }


def test_run_bridge_json_reports_the_bridges_own_words(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_" + "KEY", "provider-key-for-tests")
    script = tmp_path / "bridge.py"
    script.write_text(
        "import json, os, sys\n"
        "if sys.argv[2] == 'fail':\n"
        "    print('noise', file=sys.stderr)\n"
        "    print('buyer show: FAIL: no payment request pay-x', file=sys.stderr)\n"
        "    sys.exit(1)\n"
        "if sys.argv[2] == 'garbled':\n"
        "    print('not json')\n"
        "    sys.exit(0)\n"
        "json.dump({'argv': sys.argv[1:], 'leaked': 'OPENROUTER_API_' + 'KEY' in os.environ,\n"
        "           'stdin': sys.stdin.buffer.read().decode('utf-8')}, sys.stdout)\n"
    )
    launcher = tmp_path / ("bridge.cmd" if os.name == "nt" else "bridge")
    if os.name == "nt":
        launcher.write_text(f'@"{sys.executable}" "{script}" %*\n')
    else:
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
        launcher.chmod(0o755)
    ctx = CurrentHermesCtx(settings={"command": str(launcher), "config": "/srv/bridge.yaml"})
    out = plugin.run_bridge_json(["buyer", "ok"], ctx, timeout=30)
    assert out == {
        "argv": ["buyer", "ok", "--json", "--config", "/srv/bridge.yaml"],
        "leaked": False,
        "stdin": "",  # never Hermes' own terminal
    }
    out = plugin.run_bridge_json(["buyer", "ok"], ctx, timeout=30, input_text="café ✓\nline 2")
    assert out["stdin"].replace("\r\n", "\n") == "café ✓\nline 2"
    with pytest.raises(RuntimeError, match=r"^buyer show: FAIL: no payment request pay-x$"):
        plugin.run_bridge_json(["buyer", "fail"], ctx, timeout=30)
    with pytest.raises(RuntimeError, match="unreadable"):
        plugin.run_bridge_json(["buyer", "garbled"], ctx, timeout=30)
    missing = CurrentHermesCtx(settings={"command": str(tmp_path / "nope")})
    with pytest.raises(RuntimeError, match="not installed"):
        plugin.run_bridge_json(["buyer", "ok"], missing, timeout=30)
