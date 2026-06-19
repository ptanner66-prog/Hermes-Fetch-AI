import socket

import pytest

from hermes_fetch_ai.arg_validator import normalize_schema, validate_args
from hermes_fetch_ai.config import BridgeConfig


def cfg():
    return BridgeConfig(agent={"dev_random_seed": True})


def test_jsonschema_violation_raises_sanitized_error():
    tool = {
        "name": "t",
        "inputSchema": {
            "type": "object",
            "properties": {"a": {"type": "integer"}},
            "required": ["a"],
        },
    }
    raw_value = "user supplied sensitive prose"
    with pytest.raises(ValueError) as exc:
        validate_args(tool, {"a": raw_value}, cfg())
    assert "schema validation failed" in str(exc.value)
    assert raw_value not in str(exc.value)


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


@pytest.mark.parametrize(
    "url",
    [
        " http://127.0.0.1",
        "\thttp://127.0.0.1",
        "http://100.64.0.1/latest/meta-data/",
        "http://100.100.100.200/latest/meta-data/",
        "http://224.0.0.1/",
    ],
)
def test_url_bypass_forms_rejected(url):
    with pytest.raises(ValueError):
        validate_args({"name": "t"}, {"url": url}, cfg())


@pytest.mark.parametrize("url", ["file:///etc/passwd", "data:text/plain,hello", "ftp://example.com/x"])
def test_non_http_url_schemes_rejected(url):
    with pytest.raises(ValueError):
        validate_args({"name": "t"}, {"url": url}, cfg())


def test_dns_resolution_failure_rejected(monkeypatch):
    def fail_resolution(*args, **kwargs):
        raise socket.gaierror("no such host")

    monkeypatch.setattr(socket, "getaddrinfo", fail_resolution)

    with pytest.raises(ValueError):
        validate_args({"name": "t"}, {"url": "https://unresolvable.example.invalid"}, cfg())


def test_shell_metacharacters_rejected():
    with pytest.raises(ValueError):
        validate_args({"name": "t"}, {"value": "hello; rm -rf /"}, cfg())


@pytest.mark.parametrize("value", ["ok\nwhoami", "ok\r\nwhoami", "ok\x00whoami"])
def test_shell_control_characters_rejected(value):
    with pytest.raises(ValueError):
        validate_args({"name": "t"}, {"value": value}, cfg())


def test_url_like_dictionary_keys_rejected():
    with pytest.raises(ValueError):
        validate_args({"name": "t"}, {"file:///etc/passwd": "x"}, cfg())
