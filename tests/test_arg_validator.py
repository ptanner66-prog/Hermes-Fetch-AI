import socket
import pytest

from hermes_fetch_ai.arg_validator import normalize_schema, validate_args
from hermes_fetch_ai.config import BridgeConfig


def cfg():
    return BridgeConfig(agent={"dev_random_seed": True})


def test_jsonschema_violation_raises():
    tool = {
        "name": "t",
        "inputSchema": {
            "type": "object",
            "properties": {"a": {"type": "integer"}},
            "required": ["a"],
        },
    }
    with pytest.raises(Exception):
        validate_args(tool, {"a": "x"}, cfg())


def test_missing_schema_normalizes():
    assert normalize_schema(None) == {"type": "object", "properties": {}}


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/x",
        "http://127.0.0.1",
        "http://10.0.0.1",
        "http://169.254.1.1",
        "http://0.0.0.0",
        "http://[::1]/",
        "http://2130706433/",
    ],
)
def test_private_urls_rejected(url):
    with pytest.raises(ValueError):
        validate_args({"name": "t"}, {"url": url}, cfg())


def test_dns_private_resolution_guard(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, None, None, None, ("192.168.1.2", 0))],
    )
    with pytest.raises(ValueError):
        validate_args({"name": "t"}, {"url": "https://example.test"}, cfg())


def test_shell_metacharacters_rejected():
    with pytest.raises(ValueError):
        validate_args({"name": "t"}, {"value": "hello; rm -rf /"}, cfg())
