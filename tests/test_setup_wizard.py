"""The setup wizard: plain-language questions that write the bridge's config."""

from __future__ import annotations

import io
import json
import os
import stat
import sys
from pathlib import Path

import pytest
import yaml

from hermes_fetch_ai import cli
from hermes_fetch_ai.audit import managed_config_path
from hermes_fetch_ai.config import load_config
from hermes_fetch_ai.setup_wizard import (
    HEADER,
    ConsoleAsker,
    ScriptedAsker,
    SetupError,
    Wizard,
    agent_name,
    check_handle,
    check_price,
    read_keys,
    run_setup,
)
from hermes_fetch_ai.wallet import BUYING_WALLET_INDEX, agent_address, wallet_address

SEED = "setup-wizard-test-" + "identity-material-not-a-real-seed"
KEY = "sk-or-v1-" + "0" * 40


class Owner:
    """Stand-ins for what the wizard does outside itself: the faucet and Agentverse."""

    def __init__(self) -> None:
        self.funded: list[str] = []
        self.listed: list[tuple[str, str]] = []

    def fund(self, address: str) -> bool:
        self.funded.append(address)
        return True

    def list_on_agentverse(self, cfg, seed: str, api_key: str) -> None:
        self.listed.append((cfg.agent.name, api_key))


def wizard(tmp_path, answers, *, environ=None, owner=None, probe=None):
    asker = ScriptedAsker(answers)
    owner = owner or Owner()
    w = Wizard(
        asker,
        tmp_path / "config" / "bridge.yaml",
        environ={"UAGENT_SEED": SEED} if environ is None else environ,
        fund=owner.fund,
        list_on_agentverse=owner.list_on_agentverse,
        probe=probe or (lambda url: None),
        free_port=lambda port: True,
    )
    return w, asker, owner


@pytest.fixture
def state(tmp_path, monkeypatch):
    """The bridge's records folder (guest keys go in it)."""
    path = tmp_path / "state"
    monkeypatch.setenv("XDG_STATE_HOME", str(path))
    monkeypatch.setenv("LOCALAPPDATA", str(path))
    from hermes_fetch_ai.audit import default_state_dir

    return default_state_dir()


def load(path: Path, monkeypatch):
    monkeypatch.setenv("UAGENT_SEED", SEED)
    return load_config(path)


def program(tmp_path: Path) -> Path:
    path = tmp_path / "draft-motion"
    path.write_text("#!/bin/sh\necho drafted\n")
    path.chmod(0o755)
    return path


def test_without_the_agents_key_it_says_to_run_setup_through_hermes(tmp_path):
    w, asker, _ = wizard(tmp_path, {}, environ={})
    assert w.run() == 1
    assert "  hermes fetchai-bridge setup" in asker.said
    assert not (tmp_path / "config").exists()


def test_a_first_setup_that_sells_and_buys(tmp_path, monkeypatch, state):
    tool = program(tmp_path)
    answers = {
        "name": "Hermes Research Desk",
        "description": "Research and reviews for test FET.",
        "sell": True,
        "research": True,
        "research.provider": "openrouter",
        "research.key": KEY,
        "research.price": "0.05",
        "review": True,
        "review.model": "qwen2.5-coder:14b",
        "own": [True, False],
        "own.program": str(tool),
        "own.name": "legal-draft",
        "own.title": "Draft a motion",
        "own.description": "A first draft of a motion from your facts.",
        "own.price": "0.5",
        "own.disclaimer": "A first draft for review by a licensed attorney; not legal advice.",
        "own.example": "Draft a motion to extend the deadline by 30 days.",
        "buy": True,
        "buy.max_payment": "0.5",
        "buy.max_per_day": "3",
    }
    w, asker, owner = wizard(tmp_path, answers)
    assert w.run() == 0, asker.said
    path = tmp_path / "config" / "bridge.yaml"
    text = path.read_text()
    assert text.startswith(HEADER)
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    cfg = load(path, monkeypatch)
    assert cfg.agent.name == "hermes_research_desk"
    assert (cfg.agent.mode, cfg.agent.endpoint) == ("endpoint", "http://127.0.0.1:8000/submit")
    assert cfg.payments.enabled and not cfg.chat.enable_chat  # chat needs Agentverse
    assert cfg.policy.public_tools == []
    assert list(cfg.services) == ["research", "security-review", "legal-draft"]
    research = cfg.services["research"]
    assert research.runner.type == "hermes"
    assert (research.runner.provider, research.runner.model) == (
        "openrouter",
        "anthropic/claude-sonnet-4.6",
    )
    assert research.runner.toolsets == ["web"]
    assert research.max_runs_per_day == 20  # each request costs the owner real money
    review = cfg.services["security-review"].runner
    assert review.argv[:3] == [sys.executable, "-m", "hermes_fetch_ai.local_review"]
    assert review.argv[3:] == ["--url", "http://127.0.0.1:11434/v1", "--model", "qwen2.5-coder:14b"]
    legal = cfg.services["legal-draft"]
    assert legal.runner.argv == [str(tool)] and legal.price == "0.5"
    assert legal.disclaimer and "licensed attorney" in legal.disclaimer
    # Examples become Agentverse starter prompts, so ASI:One users can try a service.
    assert legal.example == "Draft a motion to extend the deadline by 30 days."
    assert research.example and cfg.services["security-review"].example
    assert cfg.buying.enabled
    assert (cfg.buying.max_payment, cfg.buying.max_per_day) == ("0.5", "3")
    assert cfg.buying.max_per_seller_per_day == "2"
    # The research guest's own key, kept apart from Hermes' keys, readable only by the owner.
    keys = state / "guests" / "research.env"
    assert read_keys(keys) == {"OPENROUTER_API_KEY": KEY}
    if os.name != "nt":
        assert stat.S_IMODE(keys.stat().st_mode) == 0o600
    assert KEY not in text
    # The owner is shown the agent's address and wallets, and told to keep the key safe.
    said = "\n".join(asker.said)
    assert agent_address(SEED) in said and wallet_address(SEED) in said
    assert "Keep a copy somewhere" in said
    assert "OpenRouter account, which costs real money" in said
    assert owner.funded == [wallet_address(SEED, BUYING_WALLET_INDEX)]
    assert owner.listed == []  # no Agentverse key: nothing is listed
    # The guest Hermes is found only through `hermes fetchai-bridge`.
    assert any("Hermes' Python is unknown" in line for line in asker.said)
    assert (
        "  hermes fetchai-bridge start    start your agent; it keeps running in the background"
        in (asker.said)
    )


def test_with_an_agentverse_key_the_agent_gets_a_mailbox_and_a_listing(tmp_path, monkeypatch):
    environ = {"UAGENT_SEED": SEED, "AGENTVERSE_API_KEY": "av-key"}
    answers = {"handle": "@Hermes-Reviews", "research": False, "review": True}
    w, asker, owner = wizard(tmp_path, answers, environ=environ)
    assert w.run() == 0, asker.said
    cfg = load(tmp_path / "config" / "bridge.yaml", monkeypatch)
    assert (cfg.agent.mode, cfg.agent.publish_manifest) == ("mailbox", True)
    assert cfg.agent.endpoint is None and cfg.agent.handle == "hermes-reviews"
    assert cfg.chat.enable_chat and list(cfg.services) == ["security-review"]
    assert owner.listed == [("hermes_agent", "av-key")]


def test_running_it_again_keeps_answers_and_hand_made_settings(tmp_path, monkeypatch, state):
    tool = program(tmp_path)
    first = {
        "research": True,
        "research.key": KEY,
        "research.provider": "anthropic",
        "research.per_day": "5",
        "review": False,
        "own": [True, False],
        "own.program": str(tool),
        "own.name": "legal-draft",
        "own.title": "Draft a motion",
        "own.description": "Drafts.",
        "buy": False,
    }
    w, asker, _ = wizard(tmp_path, first)
    assert w.run() == 0, asker.said
    path = tmp_path / "config" / "bridge.yaml"
    data = yaml.safe_load(path.read_text())
    data["logging"] = {"audit_path": str(tmp_path / "audit.jsonl")}  # added by hand
    path.write_text(HEADER + yaml.safe_dump(data, sort_keys=False))
    w, asker, _ = wizard(tmp_path, {})  # Enter, Enter, Enter...
    assert w.run() == 0, asker.said
    cfg = load(path, monkeypatch)
    assert list(cfg.services) == ["research", "legal-draft"]
    assert cfg.services["research"].runner.provider == "anthropic"
    assert cfg.services["research"].runner.model == "claude-sonnet-4-6"
    assert cfg.services["research"].max_runs_per_day == 5
    assert cfg.logging.audit_path == str(tmp_path / "audit.jsonl")
    assert not cfg.buying.enabled
    assert "research.keep_key" in asker.asked and "research.key" not in asker.asked
    assert "keep.legal-draft" in asker.asked


def test_a_config_setup_did_not_write_is_replaced_only_when_asked(tmp_path, monkeypatch):
    path = tmp_path / "config" / "bridge.yaml"
    path.parent.mkdir()
    path.write_text("agent:\n  name: hand_made\n")
    w, asker, _ = wizard(tmp_path, {})
    assert w.run() == 1
    assert "Nothing was changed." in asker.said
    assert path.read_text() == "agent:\n  name: hand_made\n"
    w, asker, _ = wizard(tmp_path, {"replace": True, "research": False, "review": True})
    assert w.run() == 0, asker.said
    assert path.with_name("bridge.yaml.bak").read_text() == "agent:\n  name: hand_made\n"
    assert load(path, monkeypatch).agent.name == "hand_made"  # offered as the default


def test_research_without_a_key_is_not_offered(tmp_path, monkeypatch, state):
    answers = {"research": True, "research.key": "", "review": False, "buy": False}
    w, asker, _ = wizard(tmp_path, answers)
    assert w.run() == 0, asker.said
    cfg = load(tmp_path / "config" / "bridge.yaml", monkeypatch)
    assert cfg.services == {} and not cfg.payments.enabled
    assert "No services chosen, so nothing is for sale." in asker.said


def test_research_with_a_model_on_this_computer_needs_no_key(tmp_path, monkeypatch, state):
    answers = {
        "research": True,
        "research.provider": "custom",
        "research.url": "http://localhost:1234/v1/",
        "review": False,
    }
    w, asker, _ = wizard(tmp_path, answers)
    assert w.run() == 0, asker.said
    runner = load(tmp_path / "config" / "bridge.yaml", monkeypatch).services["research"].runner
    assert (runner.provider, runner.base_url) == ("custom", "http://localhost:1234/v1")
    assert "research.key" not in asker.asked
    assert not any("costs real money" in line for line in asker.said)


def test_a_model_server_that_does_not_answer_is_pointed_out(tmp_path):
    answers = {"research": False, "review": True}
    w, asker, _ = wizard(tmp_path, answers, probe=lambda url: f"nothing answers at {url}")
    assert w.run() == 0
    assert any("nothing answers at http://127.0.0.1:11434/v1" in line for line in asker.said)


@pytest.mark.parametrize(
    ("answers", "problem"),
    [
        ({"research": False, "review": True, "review.price": "free"}, "Give a price in FET"),
        ({"research": False, "review": True, "review.url": "http://10.0.0.9/v1"}, "this computer"),
        ({"research": False, "buy": True, "buy.max_payment": "5", "buy.max_per_day": "1"}, "a day"),
        ({"research": False, "own": True, "own.program": "relative/path"}, "full path"),
    ],
)
def test_answers_it_cannot_use_are_explained(tmp_path, answers, problem):
    asker = ScriptedAsker(answers)
    code = run_setup(
        asker,
        tmp_path / "bridge.yaml",
        environ={"UAGENT_SEED": SEED},
        fund=Owner().fund,
    )
    assert code == 1
    assert problem in asker.said[-1]
    assert not (tmp_path / "bridge.yaml").exists()


def test_checks():
    assert agent_name("  Hermes Research Desk! ") == "hermes_research_desk"
    with pytest.raises(SetupError):
        agent_name("!!!")
    assert check_handle("@Hermes-Desk") == "hermes-desk" and check_handle("") == ""
    # Agentverse drops '_' and '.', so @hermes_desk would not reach the agent.
    for bad in ("ab", "-abc", "a" * 21, "héllo", "hermes_desk", "hermes.desk"):
        with pytest.raises(SetupError):
            check_handle(bad)
    assert check_price("0.050") == "0.05"
    for bad in ("0", "-1", "lots", "1000001"):
        with pytest.raises(SetupError):
            check_price(bad)


def test_the_console_asks_again_until_an_answer_fits():
    replies = iter(["", "lots", "0.2", "maybe", "y", "9", "2", ""])
    out = io.StringIO()
    asker = ConsoleAsker(read=lambda prompt: next(replies), read_secret=lambda p: " key ", out=out)
    assert asker.ask("k", "Name", default="hermes") == "hermes"
    assert asker.ask("k", "Price", default="0.1", check=check_price) == "0.2"
    assert asker.yes("k", "Sell?", False) is True
    assert asker.choose("k", "Which?", {"a": "first", "b": "second"}, "a") == "b"
    assert asker.yes("k", "Buy?", True) is True
    assert asker.secret("k", "Key") == "key"
    shown = out.getvalue()
    assert "Give a price in FET" in shown and "Please answer y or n." in shown
    assert "Please choose a number from 1 to 2." in shown and "1. first (suggested)" in shown


def test_setup_from_the_command_line(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("UAGENT_SEED", SEED)
    funded = []
    monkeypatch.setattr(cli, "_fund_from_faucet", lambda address: funded.append(address) or True)
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps({"research": False, "review": True, "buy": True}))
    assert cli.main(["setup", "--answers", str(answers)]) == 0
    out = capsys.readouterr().out
    assert f"Saved your choices to {managed_config_path()}" in out
    assert funded == [wallet_address(SEED, BUYING_WALLET_INDEX)]
    assert cli.main(["doctor"]) == 0
    assert "(written by setup)" in capsys.readouterr().out
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert cli.main(["setup"]) == 2
    assert "run it in a terminal" in capsys.readouterr().err
    answers.write_text("[1, 2]")
    assert cli.main(["setup", "--answers", str(answers)]) == 1
    assert "must be a JSON object" in capsys.readouterr().err


def test_more_checks(tmp_path):
    from hermes_fetch_ai.setup_wizard import (
        check_local_url,
        check_optional_text,
        check_program,
        check_runs_per_day,
        check_seconds,
        check_service_name,
        check_text,
    )

    assert check_service_name(" Legal-Draft ") == "legal-draft"
    for bad in ("research", "security-review", "two words", "x" * 41):
        with pytest.raises(SetupError):
            check_service_name(bad)
    assert check_local_url("http://127.0.0.1:11434/v1/") == "http://127.0.0.1:11434/v1"
    with pytest.raises(SetupError):
        check_local_url("https://api.example.com/v1")
    tool = program(tmp_path)
    assert check_program(str(tool)) == str(tool)
    script = tmp_path / "draft.py"
    script.write_text("print('hi')\n")
    assert check_program(str(script)) == str(script)  # run with the bridge's Python
    for bad in ("draft.py", str(tmp_path / "missing")):
        with pytest.raises(SetupError):
            check_program(bad)
    if os.name != "nt":
        plain = tmp_path / "plain"
        plain.write_text("x")
        with pytest.raises(SetupError, match="not executable"):
            check_program(str(plain))
    assert check_runs_per_day(" 20 ") == "20"
    for bad in ("many", "0", "2.5", "100001"):
        with pytest.raises(SetupError):
            check_runs_per_day(bad)
    assert check_seconds("90") == "90"
    for bad in ("soon", "0", "7200"):
        with pytest.raises(SetupError):
            check_seconds(bad)
    with pytest.raises(SetupError):
        check_text(5)("   ")
    with pytest.raises(SetupError):
        check_text(5)("too long")
    assert check_optional_text(5)("") == ""
    with pytest.raises(SetupError):
        check_optional_text(5)("too long")


def test_the_model_server_probe_and_the_port_check():
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from hermes_fetch_ai.setup_wizard import port_is_free, probe_model_server

    class Models(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b'{"data": []}' if self.path == "/v1/models" else b"not json"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Models)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    try:
        assert probe_model_server(f"http://127.0.0.1:{port}/v1") is None
        assert "nothing answers" in (probe_model_server(f"http://127.0.0.1:{port}/x") or "")
        assert not port_is_free(port)
    finally:
        server.shutdown()
        server.server_close()
    assert "nothing answers" in (probe_model_server(f"http://127.0.0.1:{port}/v1") or "")
    assert port_is_free(port)


def test_a_port_another_program_holds_on_127_0_0_1_is_not_free(monkeypatch):
    # macOS and Windows let the agent listen on every interface beside a program on
    # 127.0.0.1, which would then get this computer's own connections to the agent.
    from hermes_fetch_ai import setup_wizard

    tried = []

    class Socket:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def setsockopt(self, *args):
            pass

        def bind(self, address):
            tried.append(address)
            if address[0] == "127.0.0.1":
                raise OSError("address in use")

    monkeypatch.setattr(setup_wizard.socket, "socket", lambda *args: Socket())
    assert not setup_wizard.port_is_free(8001)
    assert tried == [("", 8001), ("127.0.0.1", 8001)]


def test_a_busy_port_moves_to_the_next_free_one(tmp_path, monkeypatch):
    asker = ScriptedAsker({"sell": False, "buy": False})
    w = Wizard(
        asker,
        tmp_path / "bridge.yaml",
        environ={"UAGENT_SEED": SEED},
        free_port=lambda port: port >= 8003,
    )
    assert w.run() == 0
    cfg = load(tmp_path / "bridge.yaml", monkeypatch)
    assert cfg.agent.port == 8003 and cfg.agent.endpoint == "http://127.0.0.1:8003/submit"
