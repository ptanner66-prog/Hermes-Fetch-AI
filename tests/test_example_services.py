"""The example service programs and examples/paid-services.yaml."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from hermes_fetch_ai import cli
from hermes_fetch_ai.config import (
    HERMES_PYTHON_VAR,
    HERMES_PYTHONPATH_VAR,
    CommandRunnerConfig,
    HermesRunnerConfig,
    load_config,
)
from hermes_fetch_ai.services import CommandRunner, program_problems

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
CODE_REVIEW = EXAMPLES / "services" / "code_review.py"
WORD_COUNT = EXAMPLES / "services" / "word_count.py"
FAKE_HERMES = Path(__file__).resolve().parent / "fakes" / "fake_hermes"
SEED = "example-services-test-" + "identity-material-not-real"
ANSWER = "1. eval() on user input (critical): use ast.literal_eval instead."


class FakeModelServer(ThreadingHTTPServer):
    """An OpenAI-compatible chat endpoint on 127.0.0.1 that records what it was sent."""

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _ModelHandler)
        self.requests: list[dict[str, Any]] = []

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}/v1"


class _ModelHandler(BaseHTTPRequestHandler):
    server: FakeModelServer

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append({"path": self.path, "body": body})
        data = json.dumps({"choices": [{"message": {"content": ANSWER}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:
        pass


@pytest.fixture
def model() -> Iterator[FakeModelServer]:
    server = FakeModelServer()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def run_program(
    program: Path, request: str, *args: str, **env: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(program), *args],
        input=json.dumps({"request": request}),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={**os.environ, **env},
    )


def test_code_review_asks_the_local_model_with_defensive_instructions(model):
    code = "def handler(text):\n    return eval(text)\n"
    res = run_program(CODE_REVIEW, code, "--url", model.url, "--model", "coder")
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == ANSWER
    (sent,) = model.requests
    assert sent["path"] == "/v1/chat/completions"
    system, user = sent["body"]["messages"]
    assert system["role"] == "system" and "never write a" in system["content"]
    assert "working exploit" in system["content"]
    assert user == {"role": "user", "content": code}
    assert sent["body"]["model"] == "coder" and sent["body"]["stream"] is False


@pytest.mark.parametrize(
    "url",
    ["https://api.example.com/v1", "http://10.0.0.5:11434/v1", "file:///etc/passwd", "localhost"],
)
def test_code_review_only_talks_to_this_machine(url):
    res = run_program(CODE_REVIEW, "x = 1", "--url", url)
    assert res.returncode == 2 and "on this machine" in res.stderr
    res = run_program(CODE_REVIEW, "x = 1", REVIEW_MODEL_URL=url)
    assert res.returncode == 2 and "on this machine" in res.stderr


def test_code_review_fails_retryably_when_the_model_server_is_down(unused_tcp_port):
    res = run_program(CODE_REVIEW, "x = 1", "--url", f"http://127.0.0.1:{unused_tcp_port}/v1")
    assert res.returncode == 1 and "failed" in res.stderr
    res = run_program(CODE_REVIEW, "x = 1", "--timeout", "soon")
    assert res.returncode == 2 and "number of seconds" in res.stderr


async def test_code_review_through_the_command_runner(model, monkeypatch):
    monkeypatch.setenv("REVIEW_MODEL_URL", model.url)
    runner = CommandRunner(
        CommandRunnerConfig(
            type="command", argv=[sys.executable, str(CODE_REVIEW)], pass_env=["REVIEW_MODEL_URL"]
        )
    )
    result = await runner.run("import pickle\npickle.loads(data)")
    assert result.ok and result.text.strip() == ANSWER


def test_word_count_template():
    res = run_program(WORD_COUNT, "hello there")
    assert res.returncode == 0
    assert res.stdout.strip() == "Your text has 2 words and 11 characters."


@pytest.mark.skipif(os.name == "nt", reason="the example uses POSIX paths")
def test_paid_services_example_loads_and_flags_its_placeholders(monkeypatch):
    monkeypatch.setenv("UAGENT_SEED", SEED)
    monkeypatch.delenv(HERMES_PYTHON_VAR, raising=False)
    cfg = load_config(EXAMPLES / "paid-services.yaml")
    assert cfg.payments.enabled and cfg.policy.public_tools == []
    assert list(cfg.services) == ["research", "security-review", "word-count"]
    research = cfg.services["research"].runner
    assert isinstance(research, HermesRunnerConfig)
    assert research.toolsets == ["web"] and research.python is None
    review = cfg.services["security-review"]
    assert review.input.check_urls is False and review.price == "0.1"
    assert review.runner.argv[2:] == [
        "--url",
        "http://127.0.0.1:11434/v1",
        "--model",
        "qwen2.5-coder:7b",
    ]
    assert review.disclaimer and "not a penetration test" in review.disclaimer
    problems = program_problems(cfg)
    assert any(
        "/path/to/Hermes-Fetch-AI/examples/services/code_review.py not found" in p for p in problems
    )
    # Outside `hermes fetchai-bridge`, the guest needs to be told where Hermes is.
    assert any(p.startswith("service research: Hermes' Python is unknown") for p in problems)


def test_example_with_real_paths_passes_doctor_and_try(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("UAGENT_SEED", SEED)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "state"))  # the state folder on Windows
    # The Hermes the fetchai-bridge plugin hands over: here, a stand-in.
    monkeypatch.setenv(HERMES_PYTHON_VAR, sys.executable)
    monkeypatch.setenv(HERMES_PYTHONPATH_VAR, str(FAKE_HERMES))
    text = (EXAMPLES / "paid-services.yaml").read_text(encoding="utf-8")
    text = text.replace("/usr/bin/python3", json.dumps(sys.executable))
    text = text.replace(
        "/path/to/Hermes-Fetch-AI/examples/services/code_review.py", json.dumps(str(CODE_REVIEW))
    )
    text = text.replace(
        "/path/to/Hermes-Fetch-AI/examples/services/word_count.py", json.dumps(str(WORD_COUNT))
    )
    path = tmp_path / "paid-services.yaml"
    path.write_text(text, encoding="utf-8")
    assert cli.main(["doctor", "--config", str(path)]) == 0
    out = capsys.readouterr().out
    assert "services: research 0.05 FET, security-review 0.1 FET, word-count 0.01 FET" in out
    assert "guest research: tools web; model anthropic/claude-sonnet-4 (openrouter)" in out
    assert f"{Path('guests', 'research.env')} (not there yet" in out
    args = ["seller", "try", "word-count", "--request", "hello there", "--config", str(path)]
    assert cli.main(args) == 0
    assert capsys.readouterr().out.strip() == "Your text has 2 words and 11 characters."
    args = ["seller", "try", "research", "--request", "What causes tides?", "--config", str(path)]
    assert cli.main(args) == 0
    assert capsys.readouterr().out.strip().startswith("the answer\n\n— Researched by an AI")


@pytest.mark.skipif(os.name == "nt", reason="the example uses POSIX paths")
def test_asi_one_example_sells_through_chat_on_agentverse(monkeypatch):
    from hermes_fetch_ai.agentverse import registration

    monkeypatch.setenv("UAGENT_SEED", SEED)
    cfg = load_config(EXAMPLES / "asi-one.yaml")
    assert cfg.chat.enable_chat and cfg.agent.mode == "mailbox"
    assert cfg.agent.publish_manifest and not cfg.agent.ledger_registration
    request = registration(cfg)
    assert (request.type, request.handle) == ("mailbox", "hermes-reviews")
    assert "`security-review: <your request>`" in (request.readme or "")
