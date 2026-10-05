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


@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "data:text/plain,hello", "ftp://example.com/x"]
)
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


def _public_dns(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, None, None, None, ("93.184.216.34", 0))],
    )


@pytest.mark.parametrize(
    "text", ["Note: hello", "Re: meeting at 3", "key:value", "urn:isbn:0451450523", "12:30"]
)
def test_plain_text_with_a_colon_is_not_a_url(text):
    assert validate_args({"name": "t"}, {"text": text}, cfg()) == {"text": text}


@pytest.mark.parametrize(
    "text",
    [
        "see http://169.254.169.254/latest/meta-data",
        "TODO: fix http://10.0.0.1/admin.",
        "(mirror at https://[::1]:8443/x)",
        "read file:///etc/passwd please",
    ],
)
def test_urls_inside_longer_text_are_checked(text):
    with pytest.raises(ValueError):
        validate_args({"name": "t"}, {"text": text}, cfg())


def test_public_url_inside_text_is_allowed(monkeypatch):
    _public_dns(monkeypatch)
    text = "docs at https://example.com/guide, see section 2"
    assert validate_args({"name": "t"}, {"text": text}, cfg()) == {"text": text}


@pytest.mark.parametrize(
    "value",
    ["localhost", "localhost:8080", "169.254.169.254/latest/meta-data", "10.0.0.1", "[::1]:80"],
)
def test_bare_local_hosts_are_rejected(value):
    with pytest.raises(ValueError, match="private or local"):
        validate_args({"name": "t"}, {"host": value}, cfg())


def test_bare_public_ip_is_allowed(monkeypatch):
    _public_dns(monkeypatch)
    assert validate_args({"name": "t"}, {"host": "93.184.216.34:443"}, cfg())


def test_query_strings_need_a_trusted_tool(monkeypatch):
    _public_dns(monkeypatch)
    url = "https://example.com/search?q=1&page=2"
    with pytest.raises(ValueError, match="shell metacharacters"):
        validate_args({"name": "fetch"}, {"url": url}, cfg())
    trusted = BridgeConfig(agent={"dev_random_seed": True}, policy={"trusted_shell_tools": ["fetch"]})
    assert validate_args({"name": "fetch"}, {"url": url}, trusted) == {"url": url}


def test_non_object_args_raise_type_error():
    with pytest.raises(TypeError):
        validate_args({"name": "t"}, ["not", "an", "object"], cfg())  # type: ignore[arg-type]
