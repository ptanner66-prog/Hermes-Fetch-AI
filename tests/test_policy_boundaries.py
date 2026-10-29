"""Regression tests for bounded caches and sanitized argument failures."""

import json

import pytest
from pydantic import ValidationError

from hermes_fetch_ai._redaction import redact_text
from hermes_fetch_ai.arg_validator import validate_args
from hermes_fetch_ai.config import BridgeConfig, HermesMCPConfig, PolicyConfig
from hermes_fetch_ai.policy import ReplayCache, TokenBuckets


def test_full_replay_cache_keeps_live_request_ids(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("hermes_fetch_ai.policy._clock", lambda: clock[0])
    cache = ReplayCache()
    assert cache.remember("first", 60, 1)[0]
    assert cache.remember("second", 60, 1) == (False, "replay cache full")
    assert cache.remember("first", 60, 1) == (False, "replay detected")
    clock[0] += 60
    assert cache.remember("second", 60, 1)[0]


def test_full_sender_cache_cannot_reset_an_existing_senders_quota(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("hermes_fetch_ai.policy._clock", lambda: clock[0])
    buckets = TokenBuckets()
    assert buckets.consume("first", "call", 1, 100, 1)[0]
    assert buckets.consume("second", "call", 1, 100, 1) == (False, "sender capacity reached")
    assert buckets.consume("first", "call", 1, 100, 1) == (False, "rate limit exceeded")
    assert len(buckets.global_hits["call"]) == 1
    clock[0] += 60
    assert buckets.consume("second", "call", 1, 100, 1)[0]


@pytest.mark.parametrize("field", ["replay_ttl_seconds", "max_replay_clock_skew_seconds"])
def test_replay_time_limits_must_be_finite(field):
    with pytest.raises(ValidationError):
        PolicyConfig(**{field: float("inf")})


def test_backend_timeout_must_be_finite():
    with pytest.raises(ValidationError):
        HermesMCPConfig(timeout_seconds=float("inf"))


def test_malformed_url_error_does_not_echo_raw_arguments():
    config = BridgeConfig(agent={"dev_random_seed": True})
    with pytest.raises(ValueError, match="malformed URL") as error:
        validate_args({"name": "echo"}, {"url": "https://[sensitive-input]/"}, config)
    assert "sensitive-input" not in str(error.value)


@pytest.mark.parametrize(
    "text",
    [
        "//127.0.0.1/admin",
        "please read //localhost/admin",
        "nested data:text/plain,x",
        "https://8.8.8.8/?next=http://127.0.0.1",
        "https://8.8.8.8/#file:/private",
        "https://8.8.8.8/?next=gopher://127.0.0.1",
    ],
)
def test_embedded_and_protocol_relative_local_urls_are_rejected(text):
    with pytest.raises(ValueError):
        validate_args(
            {"name": "echo"}, {"text": text}, BridgeConfig(agent={"dev_random_seed": True})
        )


@pytest.mark.parametrize("key", ["password", "api_key", "token"])
def test_redaction_handles_quoted_sensitive_keys_without_breaking_json(key):
    raw = json.dumps({key: 'sensitive-input with "quoted" text'})
    redacted = redact_text(raw)
    assert "sensitive-input" not in redacted
    assert json.loads(redacted)[key] == "[REDACTED]"
