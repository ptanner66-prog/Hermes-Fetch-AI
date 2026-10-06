"""Services: configuration, runners, and the desk that prices and runs them."""

import asyncio
import json
import os
import signal
import sys
import textwrap

import pytest
from pydantic import ValidationError

from hermes_fetch_ai import services
from hermes_fetch_ai.config import BridgeConfig, load_config
from hermes_fetch_ai.fake_ledger import FakeLedger
from hermes_fetch_ai.quotes import quote_key
from hermes_fetch_ai.seller import PaymentProof, Seller, parse_payment_terms
from hermes_fetch_ai.services import (
    CommandRunner,
    EchoRunner,
    ServiceDesk,
    ServiceResult,
    build_runner,
    service_tool,
)
from hermes_fetch_ai.store import Store

PAYOUT = "fetch1hh09pm44murgmu7rpaxluwad3way3nxq0fl6fx"


def cfg(services=None, **payments):
    return BridgeConfig.model_validate(
        {
            "agent": {"dev_random_seed": True},
            "payments": {"enabled": True, "payout_address": PAYOUT, **payments},
            "services": services
            if services is not None
            else {
                "research": {
                    "title": "Research a topic",
                    "description": "Finds and summarizes sources.",
                    "price": "0.05",
                    "runner": {"type": "echo"},
                    "disclaimer": "Check the sources yourself.",
                },
                "free": {
                    "title": "Say hello",
                    "description": "Free.",
                    "runner": {"type": "echo"},
                    "max_runs_per_day": 2,
                },
            },
        }
    )


# -- configuration ------------------------------------------------------------


def test_services_need_payments_enabled():
    with pytest.raises(ValidationError, match="payments.enabled"):
        BridgeConfig.model_validate(
            {
                "agent": {"dev_random_seed": True},
                "services": {"x": {"title": "t", "description": "d", "runner": {"type": "echo"}}},
            }
        )


@pytest.mark.parametrize(
    ("payments", "agent", "message"),
    [
        ({"network": "mainnet"}, {}, "mainnet is locked"),
        ({}, {"network": "mainnet"}, "testnet only"),
        ({"payout_address": None}, {}, "payout_address"),
        ({"payout_address": "fetch1notanaddress"}, {}, "fetch1"),
        ({"ledger_url": "http://rest-dorado.fetch.ai"}, {}, "https"),
        ({"ledger_url": "https://user:pw@ledger.example"}, {}, "credentials"),
        ({"ledger_url": "ftp://ledger.example"}, {}, "https"),
    ],
)
def test_payment_settings_are_validated(payments, agent, message):
    with pytest.raises(ValidationError, match=message):
        BridgeConfig.model_validate(
            {
                "agent": {"dev_random_seed": True, **agent},
                "payments": {"enabled": True, "payout_address": PAYOUT, **payments},
            }
        )


def test_loopback_ledger_url_may_use_http():
    c = cfg(ledger_url="http://127.0.0.1:1317/")
    assert c.payments.ledger_url == "http://127.0.0.1:1317"


@pytest.mark.parametrize(
    ("service", "message"),
    [
        ({"price": "0.1e1"}, "not a FET amount"),
        ({"price": "1001"}, "at most 1000"),
        ({"price": 0.05}, "string"),
        ({"runner": {"type": "command", "argv": ["relative/program"]}}, "absolute path"),
        (
            {"runner": {"type": "command", "argv": ["/bin/x"], "pass_env": ["NOT VALID"]}},
            "environment",
        ),
        ({"runner": {"type": "shell"}}, "type"),
        ({"title": ""}, "title"),
    ],
)
def test_service_settings_are_validated(service, message):
    base = {"title": "t", "description": "d", "runner": {"type": "echo"}}
    with pytest.raises(ValidationError, match=message):
        cfg({"svc": {**base, **service}})


def test_relative_program_error_suggests_the_absolute_path(monkeypatch):
    base = {"title": "t", "description": "d"}
    runner = {"type": "command", "argv": ["python3", "service.py"]}
    monkeypatch.setattr("shutil.which", lambda name: f"/opt/bin/{name}")
    with pytest.raises(ValidationError, match="absolute path, such as /opt/bin/python3"):
        cfg({"svc": {**base, "runner": runner}})
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(ValidationError, match=r"must be an absolute path \[type"):
        cfg({"svc": {**base, "runner": runner}})


@pytest.mark.parametrize("name", ["Upper", "has space", "dots.not.allowed", "x" * 41, "-lead"])
def test_service_names_are_validated(name):
    with pytest.raises(ValidationError, match="service name"):
        cfg({name: {"title": "t", "description": "d", "runner": {"type": "echo"}}})


def test_service_names_with_secret_words_are_not_flagged(tmp_path, monkeypatch):
    path = tmp_path / "c.yaml"
    path.write_text(
        textwrap.dedent(
            f"""
            agent: {{dev_random_seed: true}}
            payments: {{enabled: true, payout_address: {PAYOUT}}}
            services:
              token-research:
                title: Token research
                description: Research crypto tokens.
                price: "0.01"
                runner: {{type: echo}}
            """
        )
    )
    assert "token-research" in load_config(path).services


# -- runners --------------------------------------------------------------------


async def test_echo_runner():
    assert await EchoRunner().run("hi") == ServiceResult("hi", ok=True)


def program(tmp_path, body):
    script = tmp_path / "service.py"
    script.write_text(textwrap.dedent(body))
    return [sys.executable, str(script)]


def command_runner(argv, **overrides):
    runner = build_runner(
        cfg(
            {
                "svc": {
                    "title": "t",
                    "description": "d",
                    "runner": {"type": "command", "argv": argv, **overrides},
                }
            }
        )
        .services["svc"]
        .runner
    )
    assert isinstance(runner, CommandRunner)
    return runner


async def test_command_runner_passes_json_and_returns_stdout(tmp_path):
    argv = program(
        tmp_path,
        """
        import json, os, sys
        request = json.load(sys.stdin)["request"]
        print(f"got {request} in {os.path.basename(os.getcwd())}", end="")
        """,
    )
    result = await command_runner(argv).run("a; rm -rf / && $(boom)")
    assert result.ok
    assert result.text.startswith("got a; rm -rf / && $(boom) in hermes-fetch-ai-service-")


async def test_command_runner_gets_only_allowlisted_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("UAGENT_SEED", "must-not-leak-to-services-at-all-ever")
    monkeypatch.setenv("SERVICE_TOKEN", "allowed")
    argv = program(
        tmp_path,
        """
        import json, os
        print(json.dumps(sorted(os.environ)))
        """,
    )
    result = await command_runner(argv, pass_env=["SERVICE_TOKEN"]).run("x")
    names = set(json.loads(result.text))
    assert "UAGENT_SEED" not in names
    assert {"SERVICE_TOKEN", "HOME", "TMPDIR"} <= names


async def test_command_runner_failures(tmp_path):
    failing = program(tmp_path, "import sys; sys.exit(3)")
    result = await command_runner(failing).run("x")
    assert not result.ok and "exit 3" in result.problem
    slow = program(tmp_path, "import time; time.sleep(30)")
    result = await command_runner(slow, timeout_seconds=0.5).run("x")
    assert not result.ok and "too long" in result.problem
    missing = await command_runner([str(tmp_path / "does-not-exist")]).run("x")
    assert not missing.ok and "could not start" in missing.problem


async def test_command_runner_caps_output(tmp_path):
    loud = program(tmp_path, "import sys; sys.stdout.write('x' * 1_000_000)")
    result = await command_runner(loud, max_output_chars=100).run("x")
    assert result.ok
    assert result.text.startswith("x" * 100) and result.text.endswith("[…answer truncated]")


async def test_stopping_a_program_reads_off_the_output_nobody_read(tmp_path):
    # asyncio's wait() also waits for the output pipe to close. Unread output
    # pauses the pipe, so a plain kill-and-wait would hang here.
    runner = command_runner(
        program(tmp_path, "import sys, time\nsys.stdout.write('x' * 400_000)\ntime.sleep(60)")
    )
    process = await asyncio.create_subprocess_exec(
        *runner.cfg.argv,
        stdout=asyncio.subprocess.PIPE,
        start_new_session=os.name != "nt",
    )
    await asyncio.sleep(0.5)  # the unread output fills the buffer and pauses the pipe
    await asyncio.wait_for(runner._stop(process), 3)  # well under _STOP_SECONDS
    assert process.returncode is not None


@pytest.mark.skipif(os.name == "nt", reason="needs fork and sessions")
async def test_command_runner_gives_up_on_a_child_that_escapes_the_kill(tmp_path, monkeypatch):
    monkeypatch.setattr(services, "_STOP_SECONDS", 0.5)
    pid_file = tmp_path / "escaped.pid"
    argv = program(
        tmp_path,
        f"""
        import os, time
        if os.fork() == 0:
            os.setsid()  # leaves the process group the runner kills; stdout stays open
            with open({str(pid_file)!r}, "w") as f:
                f.write(str(os.getpid()))
        time.sleep(60)
        """,
    )
    try:
        result = await command_runner(argv, timeout_seconds=0.5).run("x")
        assert not result.ok and "too long" in result.problem
    finally:
        if pid_file.exists():
            os.kill(int(pid_file.read_text()), signal.SIGKILL)
            await asyncio.sleep(0.2)  # let the loop see the pipe close


# -- the desk -----------------------------------------------------------------------


@pytest.fixture
def ledger():
    return FakeLedger()


@pytest.fixture
def desk(tmp_path, ledger):
    c = cfg()
    seller = Seller(
        payments=c.payments,
        store=Store.open(tmp_path / "payments.sqlite3"),
        key=quote_key("only for these tests, at least thirty-two characters"),
        payout=PAYOUT,
        ledger_factory=lambda: ledger,
    )
    d = ServiceDesk(c, seller)
    yield d
    seller.store.close()


def remember_ok():
    return True, "ok"


async def call(
    desk, tool, request="hello", proof=None, sender="agent1qbuyer", remember=remember_ok
):
    return await desk.call(
        sender=sender,
        tool_name=tool,
        args={"request": request},
        proof=proof,
        remember_replay=remember,
    )


def test_tools_describe_price_and_input(desk):
    tools = {t["name"]: t for t in desk.tools("agent1qbuyer")}
    assert set(tools) == {"service.research", "service.free"}
    research = tools["service.research"]
    assert "0.05 testnet FET" in research["description"]
    assert research["_meta"]["hermes_fetch_ai"]["price"] == "0.05"
    assert research["inputSchema"]["required"] == ["request"]
    assert "Free." in tools["service.free"]["description"]


def test_paused_or_banned_hides_services(desk):
    desk.seller.store.ban("agent1qspam", reason="spam", now_ms=1)
    assert desk.tools("agent1qspam") == []
    desk.seller.store.set_paused(True)
    assert desk.tools("agent1qbuyer") == []


async def test_free_service_runs_and_counts_toward_the_daily_cap(desk):
    first = await call(desk, "service.free")
    assert (first.is_error, first.text, first.decision) == (False, "hello", "allowed")
    await call(desk, "service.free")
    capped = await call(desk, "service.free")
    assert capped.is_error and "limit for today" in capped.text


async def test_paid_service_flow(desk, ledger):
    first = await call(desk, "service.research")
    assert first.decision == "payment" and first.audit["payment"] == "required"
    terms = parse_payment_terms(first.text)
    tx_hash = ledger.pay(
        payer="fetch1buyerwallet",
        recipient=terms["recipient"],
        amount_base=int(terms["amount_base"]),
        memo=terms["memo"],
    )
    proof = PaymentProof(terms["reference"], tx_hash)
    paid = await call(desk, "service.research", proof=proof)
    assert not paid.is_error
    assert paid.text == "hello\n\n— Check the sources yourself."
    assert paid.audit["payment"] == "verified" and paid.audit["tx_short"].endswith(tx_hash[-4:])
    again = await call(desk, "service.research", proof=proof)
    assert again.is_error and "already used" in again.text


async def test_paid_request_must_match_the_quote(desk, ledger):
    terms = parse_payment_terms((await call(desk, "service.research", request="one")).text)
    tx_hash = ledger.pay(
        payer="fetch1buyerwallet",
        recipient=terms["recipient"],
        amount_base=int(terms["amount_base"]),
        memo=terms["memo"],
    )
    other = await call(
        desk, "service.research", request="two", proof=PaymentProof(terms["reference"], tx_hash)
    )
    assert other.is_error and "does not match" in other.text


async def test_runner_failure_keeps_the_payment_for_a_retry(desk, ledger):
    class Flaky:
        def __init__(self):
            self.calls = 0

        async def run(self, request):
            self.calls += 1
            if self.calls == 1:
                return ServiceResult("", ok=False, problem="the service took too long")
            if self.calls == 2:
                raise RuntimeError("bug")
            return ServiceResult("finally", ok=True)

    desk.runners["research"] = Flaky()
    terms = parse_payment_terms((await call(desk, "service.research")).text)
    tx_hash = ledger.pay(
        payer="fetch1buyerwallet",
        recipient=terms["recipient"],
        amount_base=int(terms["amount_base"]),
        memo=terms["memo"],
    )
    proof = PaymentProof(terms["reference"], tx_hash)
    first = await call(desk, "service.research", proof=proof)
    assert first.is_error and "payment is kept" in first.text
    second = await call(desk, "service.research", proof=proof)
    assert second.is_error and "the service failed" in second.text
    third = await call(desk, "service.research", proof=proof)
    assert third.text.startswith("finally")


async def test_replay_refusal_leaves_the_credit_unused(desk, ledger):
    terms = parse_payment_terms((await call(desk, "service.research")).text)
    tx_hash = ledger.pay(
        payer="fetch1buyerwallet",
        recipient=terms["recipient"],
        amount_base=int(terms["amount_base"]),
        memo=terms["memo"],
    )
    proof = PaymentProof(terms["reference"], tx_hash)
    refused = await call(
        desk, "service.research", proof=proof, remember=lambda: (False, "replay detected")
    )
    assert refused.is_error and refused.text == "replay detected"
    assert desk.seller.store.credit(terms["reference"]).status == "paid"
    assert not (await call(desk, "service.research", proof=proof)).is_error


async def test_paused_banned_and_invalid_requests_are_refused(desk):
    too_long = await call(desk, "service.research", request="x" * 5000)
    assert too_long.is_error and "schema validation failed" in too_long.text
    desk.seller.store.ban("agent1qspam", reason="spam", now_ms=1)
    assert "does not accept" in (await call(desk, "service.research", sender="agent1qspam")).text
    desk.seller.store.set_paused(True)
    assert "not taking requests" in (await call(desk, "service.research")).text


async def test_url_checks_apply_unless_turned_off(tmp_path, ledger):
    services = {
        "fetcher": {"title": "t", "description": "d", "runner": {"type": "echo"}},
        "review": {
            "title": "t",
            "description": "d",
            "runner": {"type": "echo"},
            "input": {"check_urls": False},
        },
    }
    c = cfg(services)
    seller = Seller(
        payments=c.payments,
        store=Store.open(tmp_path / "p.sqlite3"),
        key=b"k" * 32,
        payout=PAYOUT,
        ledger_factory=lambda: ledger,
    )
    d = ServiceDesk(c, seller)
    code = "requests.get('http://127.0.0.1:8080/admin')"
    assert "private or local" in (await call(d, "service.fetcher", request=code)).text
    assert (await call(d, "service.review", request=code)).text == code
    seller.store.close()


def test_service_tool_for_free_service():
    c = cfg()
    tool = service_tool("free", c.services["free"], c)
    assert tool["_meta"]["hermes_fetch_ai"]["price"] == "0"
