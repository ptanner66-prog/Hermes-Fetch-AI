import json
import time

import pytest
from uagents import Model
from uagents_adapter.mcp.protocol import CallTool, ListTools

from hermes_fetch_ai.audit import AuditWriter
from hermes_fetch_ai.config import BridgeConfig
from hermes_fetch_ai.direct_protocol import build_protocol, handle_call_tool, handle_list_tools
from hermes_fetch_ai.policy import ReplayCache


def replay_args(args, request_id="req-default-0001"):
    return {
        **args,
        "_hermes_fetch_ai": {
            "request_id": request_id,
            "issued_at_ms": int(time.time() * 1000),
        },
    }


class Shim:
    def __init__(self):
        self.calls = 0
        self.list_calls = 0
        self.last_args = None

    async def list_tools(self):
        self.list_calls += 1
        return [
            {
                "name": "echo",
                "inputSchema": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            }
        ]

    async def call_tool(self, name, args):
        self.calls += 1
        self.last_args = args
        from hermes_fetch_ai.result_normalizer import NormalizedToolResult

        return NormalizedToolResult(args["text"], None, False, False, len(args["text"]))


class TruncatingShim(Shim):
    async def call_tool(self, name, args):
        self.calls += 1
        self.last_args = args
        from hermes_fetch_ai.result_normalizer import NormalizedToolResult

        return NormalizedToolResult("xxxxx", None, False, True, 123)


class Ctx:
    def __init__(self, sender="agent1qabcdefghijklmnopqrstuvwxyz0123456789"):
        self.sender = sender
        self.sent = []
        self.fail_send = False

    async def send(self, destination, message):
        if self.fail_send:
            raise RuntimeError("send boom")
        self.sent.append((destination, message))


def cfg(**policy):
    return BridgeConfig(agent={"dev_random_seed": True}, policy=policy)


@pytest.mark.asyncio
async def test_denied_call_does_not_invoke_shim(tmp_path):
    s = Shim()
    audit = AuditWriter(tmp_path / "a.jsonl")
    resp = await handle_call_tool(
        None,
        "sender",
        CallTool(tool="echo", args={"text": "x"}),
        s,
        cfg(public_tools=[]),
        audit,
    )
    assert resp.error and s.calls == 0 and audit.count() == 1


@pytest.mark.asyncio
async def test_oversize_args_denied_before_shim(tmp_path):
    s = Shim()
    resp = await handle_call_tool(
        None,
        "sender",
        CallTool(tool="echo", args={"text": "xxxx"}),
        s,
        cfg(public_tools=["echo"], max_args_bytes=5),
        AuditWriter(tmp_path / "a.jsonl"),
    )
    assert resp.error and s.calls == 0


@pytest.mark.asyncio
async def test_allowed_call_requires_replay_metadata_before_shim(tmp_path):
    s = Shim()
    resp = await handle_call_tool(
        None,
        "sender",
        CallTool(tool="echo", args={"text": "ok"}),
        s,
        cfg(public_tools=["echo"]),
        AuditWriter(tmp_path / "a.jsonl"),
        replay_cache=ReplayCache(),
    )
    assert resp.error == "missing replay metadata"
    assert s.calls == 0


@pytest.mark.asyncio
async def test_replayed_request_id_is_denied_before_shim(tmp_path):
    s = Shim()
    replay_cache = ReplayCache()
    c = cfg(public_tools=["echo"])
    audit = AuditWriter(tmp_path / "a.jsonl")

    first = await handle_call_tool(
        None,
        "sender",
        CallTool(tool="echo", args=replay_args({"text": "first"}, "req-replay-0001")),
        s,
        c,
        audit,
        replay_cache=replay_cache,
    )
    second = await handle_call_tool(
        None,
        "sender",
        CallTool(tool="echo", args=replay_args({"text": "changed"}, "req-replay-0001")),
        s,
        c,
        audit,
        replay_cache=replay_cache,
    )

    assert first.result == "first"
    assert second.error == "replay detected"
    assert s.calls == 1
    assert s.last_args == {"text": "first"}


@pytest.mark.asyncio
async def test_stale_replay_metadata_is_denied_before_shim(tmp_path):
    s = Shim()
    stale = {
        "text": "old",
        "_hermes_fetch_ai": {
            "request_id": "req-stale-0001",
            "issued_at_ms": int((time.time() - 3600) * 1000),
        },
    }
    resp = await handle_call_tool(
        None,
        "sender",
        CallTool(tool="echo", args=stale),
        s,
        cfg(public_tools=["echo"], replay_ttl_seconds=60),
        AuditWriter(tmp_path / "a.jsonl"),
        replay_cache=ReplayCache(),
    )
    assert resp.error == "stale replay metadata"
    assert s.calls == 0


@pytest.mark.asyncio
async def test_arg_validation_failure_denies_before_shim(tmp_path):
    s = Shim()
    resp = await handle_call_tool(
        None,
        "sender",
        CallTool(tool="echo", args=replay_args({}, "req-invalid-0001")),
        s,
        cfg(public_tools=["echo"]),
        AuditWriter(tmp_path / "a.jsonl"),
        replay_cache=ReplayCache(),
    )
    assert resp.error and s.calls == 0


@pytest.mark.asyncio
async def test_schema_validation_error_does_not_leak_raw_args_to_response_or_audit(tmp_path):
    s = Shim()
    audit = AuditWriter(tmp_path / "a.jsonl")
    raw_value = "sensitive prose that must not be logged"
    resp = await handle_call_tool(
        None,
        "sender",
        CallTool(tool="echo", args=replay_args({"text": {"raw": raw_value}}, "req-schema-0001")),
        s,
        cfg(public_tools=["echo"]),
        audit,
        replay_cache=ReplayCache(),
    )
    text = (tmp_path / "a.jsonl").read_text(encoding="utf-8")
    assert resp.error == "schema validation failed"
    assert raw_value not in resp.error
    assert raw_value not in text
    assert s.calls == 0


@pytest.mark.asyncio
async def test_schema_validation_error_does_not_leak_raw_property_names(tmp_path):
    s = Shim()
    audit = AuditWriter(tmp_path / "a.jsonl")
    raw_key = "sensitive prose property name"
    resp = await handle_call_tool(
        None,
        "sender",
        CallTool(tool="echo", args=replay_args({raw_key: {"bad": "shape"}}, "req-schema-key-0001")),
        s,
        cfg(public_tools=["echo"]),
        audit,
        replay_cache=ReplayCache(),
    )
    text = (tmp_path / "a.jsonl").read_text(encoding="utf-8")
    assert resp.error == "schema validation failed"
    assert raw_key not in resp.error
    assert raw_key not in text
    assert s.calls == 0


@pytest.mark.asyncio
async def test_invalid_schema_request_id_does_not_poison_valid_retry(tmp_path):
    s = Shim()
    replay_cache = ReplayCache()
    c = cfg(public_tools=["echo"])
    audit = AuditWriter(tmp_path / "a.jsonl")

    invalid = await handle_call_tool(
        None,
        "sender",
        CallTool(tool="echo", args=replay_args({"text": {"bad": "shape"}}, "req-retry-0001")),
        s,
        c,
        audit,
        replay_cache=replay_cache,
    )
    retry = await handle_call_tool(
        None,
        "sender",
        CallTool(tool="echo", args=replay_args({"text": "fixed"}, "req-retry-0001")),
        s,
        c,
        audit,
        replay_cache=replay_cache,
    )

    assert invalid.error == "schema validation failed"
    assert retry.result == "fixed"
    assert s.calls == 1


@pytest.mark.asyncio
async def test_invalid_call_consumes_rate_before_validation(tmp_path):
    s = Shim()
    c = cfg(public_tools=["echo"], max_calls_per_minute_per_sender=1)
    audit = AuditWriter(tmp_path / "a.jsonl")

    invalid = await handle_call_tool(
        None,
        "sender",
        CallTool(tool="bad\nname", args={"text": "x"}),
        s,
        c,
        audit,
    )
    assert invalid.error

    denied = await handle_call_tool(
        None,
        "sender",
        CallTool(tool="echo", args=replay_args({"text": "ok"}, "req-rate-0001")),
        s,
        c,
        audit,
        replay_cache=ReplayCache(),
    )
    assert denied.error == "rate limit exceeded"
    assert s.calls == 0


@pytest.mark.asyncio
async def test_unknown_sender_list_tools_public_only(tmp_path):
    resp = await handle_list_tools(
        None,
        "sender",
        Shim(),
        cfg(public_tools=["echo"]),
        AuditWriter(tmp_path / "a.jsonl"),
    )
    assert len(resp.tools) == 1


@pytest.mark.asyncio
async def test_list_tools_response_size_cap(tmp_path):
    resp = await handle_list_tools(
        None,
        "sender",
        Shim(),
        cfg(public_tools=["echo"], max_list_tools_response_bytes=1),
        AuditWriter(tmp_path / "a.jsonl"),
    )
    assert resp.error


@pytest.mark.asyncio
async def test_list_tools_rate_limit_denies_before_shim(tmp_path):
    s = Shim()
    c = cfg(public_tools=["echo"], max_list_tools_per_minute_per_sender=1)
    audit = AuditWriter(tmp_path / "a.jsonl")
    assert (await handle_list_tools(None, "rate_sender", s, c, audit)).tools
    denied = await handle_list_tools(None, "rate_sender", s, c, audit)
    assert denied.error == "rate limit exceeded"
    assert s.list_calls == 1


@pytest.mark.asyncio
async def test_audit_written_for_allowed_even_if_send_fails(tmp_path):
    audit = AuditWriter(tmp_path / "a.jsonl")
    resp = await handle_call_tool(
        None,
        "sender",
        CallTool(tool="echo", args=replay_args({"text": "ok"}, "req-audit-0001")),
        Shim(),
        cfg(public_tools=["echo"]),
        audit,
        replay_cache=ReplayCache(),
    )
    assert resp.result == "ok" and audit.count() == 1


@pytest.mark.asyncio
async def test_call_tool_audit_uses_normalized_truncation_metadata(tmp_path):
    audit = AuditWriter(tmp_path / "a.jsonl")
    resp = await handle_call_tool(
        None,
        "sender",
        CallTool(tool="echo", args=replay_args({"text": "ok"}, "req-trunc-0001")),
        TruncatingShim(),
        cfg(public_tools=["echo"]),
        audit,
        replay_cache=ReplayCache(),
    )
    assert resp.result == "xxxxx"
    event = json.loads((tmp_path / "a.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert event["output_bytes"] == 123
    assert event["truncated"] is True


@pytest.mark.asyncio
async def test_build_protocol_audits_send_success_and_failure(tmp_path):
    c = cfg(public_tools=["echo"])
    audit = AuditWriter(tmp_path / "a.jsonl")
    proto = build_protocol(Shim(), c, audit)
    list_handler = proto.signed_message_handlers[Model.build_schema_digest(ListTools())]

    ok_ctx = Ctx()
    await list_handler(ok_ctx, ListTools())
    assert ok_ctx.sent

    fail_ctx = Ctx()
    fail_ctx.fail_send = True
    with pytest.raises(RuntimeError):
        await list_handler(fail_ctx, ListTools())

    lines = (tmp_path / "a.jsonl").read_text(encoding="utf-8").splitlines()
    assert any(json.loads(line).get("send_status") == "success" for line in lines)
    assert any(json.loads(line).get("send_status") == "failure" for line in lines)


@pytest.mark.asyncio
async def test_direct_protocol_audit_redacts_long_sender(tmp_path):
    sender = "agent1qabcdefghijklmnopqrstuvwxyz0123456789abcdefghijklmnopqrstuvwxyz"
    audit = AuditWriter(tmp_path / "a.jsonl")
    await handle_call_tool(
        None,
        sender,
        CallTool(tool="echo", args=replay_args({"text": "ok"}, "req-redact-0001")),
        Shim(),
        cfg(public_tools=["echo"]),
        audit,
        replay_cache=ReplayCache(),
    )
    text = (tmp_path / "a.jsonl").read_text(encoding="utf-8")
    assert sender not in text
    assert "…" in text
