"""Listing a selling bridge on Agentverse, offline (the Agentverse API is faked)."""

import textwrap

import pytest
from uagents_core.utils.registration import AgentverseRequestError

from hermes_fetch_ai import agentverse, cli
from hermes_fetch_ai.config import BridgeConfig
from hermes_fetch_ai.wallet import agent_address

SEED = "agentverse-test-" + "identity-material-not-a-real-seed"
API_KEY = "av-test-key-" + "not-a-real-key-0123456789"
CHAT_DIGEST = "proto:30a801ed3a83f9a0ff0a9f1e6fe958cb91da1fc2218b153df7b6cbf87bd33d62"


@pytest.fixture(autouse=True)
def stable_seed(clear_seed, monkeypatch):
    # A mailbox agent needs a stable identity.
    monkeypatch.setenv("UAGENT_SEED", SEED)


def config(**agent):
    return BridgeConfig.model_validate(
        {
            "agent": {"name": "hermes_seller", "mode": "mailbox", **agent},
            "payments": {
                "enabled": True,
                "payout_address": "fetch1hh09pm44murgmu7rpaxluwad3way3nxq0fl6fx",
            },
            "chat": {"enable_chat": True},
            "services": {
                "security-review": {
                    "title": "Defensive code security review",
                    "description": "Reviews code you send.",
                    "price": "0.1",
                    "runner": {"type": "echo"},
                    "disclaimer": "Not a penetration test.",
                }
            },
        }
    )


def test_readme_tells_asi_one_what_is_sold_and_how_to_order():
    text = agentverse.readme(config())
    assert text.startswith("# hermes_seller\n")
    assert "- **Defensive code security review** (`security-review`), 0.1 testnet FET" in text
    assert "`security-review: <your request>`" in text
    assert "Testnet FET only (Dorado)" in text
    assert "- Defensive code security review: Not a penetration test." in text


def test_a_mailbox_agent_registers_the_mailbox_and_its_protocols():
    request = agentverse.registration(config(handle="hermes-reviews"))
    assert request.endpoint == "https://agentverse.ai/v2/agents/mailbox/submit"
    assert request.type == "mailbox" and request.handle == "hermes-reviews"
    assert request.protocols[0] == CHAT_DIGEST and len(request.protocols) == 3
    assert request.starter_prompts == [
        "What services do you offer, and what do they cost?",
        "security-review: <your request>",
    ]
    assert request.active is True


def test_an_endpoint_agent_needs_a_public_endpoint():
    request = agentverse.registration(
        config(mode="endpoint", endpoint="https://bridge.example.com/submit")
    )
    assert (request.endpoint, request.type) == ("https://bridge.example.com/submit", "uagent")
    with pytest.raises(ValueError, match="Agentverse needs to reach the agent"):
        agentverse.registration(config(mode="endpoint"))


def test_register_passes_the_key_and_the_seed_to_agentverse():
    calls = []

    def fake(request, av_config, credentials):
        calls.append((request.name, av_config.url, credentials))
        return True

    agentverse.register(config(), SEED, API_KEY, register_fn=fake)
    ((name, url, credentials),) = calls
    assert (name, url) == ("hermes_seller", "https://agentverse.ai")
    assert (credentials.agentverse_api_key, credentials.agent_seed_phrase) == (API_KEY, SEED)


@pytest.mark.parametrize("handle", ["ab", "Has-Caps", "x" * 21, "-lead", "has space"])
def test_handles_are_short_lowercase_names(handle):
    with pytest.raises(ValueError, match="handle"):
        config(handle=handle)


@pytest.fixture
def chat_config(tmp_path):
    path = tmp_path / "chat.yaml"
    path.write_text(
        textwrap.dedent(
            """
            agent: {name: hermes_seller, mode: mailbox, handle: hermes-reviews}
            payments: {enabled: true}
            chat: {enable_chat: true}
            services:
              review:
                title: Review
                description: Reviews code.
                price: "0.1"
                runner: {type: echo}
            """
        ),
        encoding="utf-8",
    )
    return str(path)


def test_cli_registers_with_yes(chat_config, monkeypatch, capsys):
    calls = []
    monkeypatch.setenv(agentverse.API_KEY_VAR, API_KEY)
    monkeypatch.setattr(agentverse, "register_agent", lambda *args: calls.append(args) or True)
    assert cli.main(["agentverse", "register", "--yes", "--config", chat_config]) == 0
    out = capsys.readouterr()
    assert f"listed hermes_seller as a mailbox agent ({agent_address(SEED)})" in out.out
    assert "write to @hermes-reviews" in out.out
    assert API_KEY not in out.out + out.err and SEED not in out.out + out.err
    assert len(calls) == 1


def test_cli_asks_first_and_never_waits_when_unattended(chat_config, monkeypatch, capsys):
    monkeypatch.setenv(agentverse.API_KEY_VAR, API_KEY)
    monkeypatch.setattr(agentverse, "register_agent", lambda *args: pytest.fail("registered"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert cli.main(["agentverse", "register", "--config", chat_config]) == 2
    assert "confirm with --yes" in capsys.readouterr().err
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    assert cli.main(["agentverse", "register", "--config", chat_config]) == 1
    assert "nothing was registered" in capsys.readouterr().out


def test_cli_needs_a_key_chat_and_a_stable_identity(chat_config, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv(agentverse.API_KEY_VAR, raising=False)
    assert cli.main(["agentverse", "register", "--yes", "--config", chat_config]) == 1
    assert "set AGENTVERSE_API_KEY" in capsys.readouterr().err
    no_chat = tmp_path / "no-chat.yaml"
    no_chat.write_text("agent: {name: plain}\n", encoding="utf-8")
    assert cli.main(["agentverse", "register", "--yes", "--config", str(no_chat)]) == 1
    assert "set chat.enable_chat: true" in capsys.readouterr().err


def test_cli_reports_agentverse_errors(chat_config, monkeypatch, capsys):
    monkeypatch.setenv(agentverse.API_KEY_VAR, API_KEY)

    def refuse(*args):
        raise AgentverseRequestError("HTTP 401: invalid API key", from_exc=None)

    monkeypatch.setattr(agentverse, "register_agent", refuse)
    assert cli.main(["agentverse", "register", "--yes", "--config", chat_config]) == 1
    err = capsys.readouterr().err
    assert "agentverse: FAIL: HTTP 401: invalid API key" in err and API_KEY not in err


def test_an_agent_that_only_buys_gets_a_mailbox_too():
    # Agents elsewhere can answer Hermes only through the agent's Agentverse mailbox.
    cfg = BridgeConfig.model_validate(
        {"agent": {"name": "hermes_buyer", "mode": "mailbox"}, "buying": {"enabled": True}}
    )
    request = agentverse.registration(cfg)
    assert request.type == "mailbox"
    assert "it sells nothing" in (request.readme or "")
    assert request.starter_prompts is None
    assert len(request.protocols) == 3  # chat, payment as a buyer, MCP
    assert request.protocols != agentverse.registration(config()).protocols


def test_cli_registers_an_agent_that_only_buys(tmp_path, monkeypatch, capsys):
    path = tmp_path / "buyer.yaml"
    path.write_text("agent: {name: hermes_buyer, mode: mailbox}\nbuying: {enabled: true}\n")
    monkeypatch.setenv("AGENTVERSE_API_KEY", API_KEY)
    calls = []
    monkeypatch.setattr(agentverse, "register_agent", lambda *a: calls.append(a) or True)
    assert cli.main(["agentverse", "register", "--config", str(path), "--yes"]) == 0
    assert len(calls) == 1
    path.write_text("agent: {name: hermes_quiet, mode: mailbox}\n")
    assert cli.main(["agentverse", "register", "--config", str(path), "--yes"]) == 1
    assert "neither sells through chat nor buys" in capsys.readouterr().err
