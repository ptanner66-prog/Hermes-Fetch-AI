import json
import time

import pytest
from uagents import Model
from uagents_adapter.mcp.protocol import CallTool, ListTools

from hermes_fetch_ai import direct_protocol, policy
from hermes_fetch_ai.audit import AuditWriter
from hermes_fetch_ai.config import BridgeConfig
from hermes_fetch_ai.direct_protocol import build_protocol, handle_call_tool, handle_list_tools
from hermes_fetch_ai.policy import PolicyState
from hermes_fetch_ai.result_normalizer import NormalizedToolResult
from hermes_fetch_ai.tool_names import MAX_TOOL_NAME_LENGTH


def replay_args(args, request_id="req-default-0001", issued_at_ms=None):
    return {
        **args,
        "_hermes_fetch_ai": {
            "request_id": request_id,
            "issued_at_ms": int(time.time() * 1000) if issued_at_ms is None else issued_at_ms,
        },
    }


ECHO = {
    "name": "echo",
    "inputSchema": {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
}


class Shim:
    tools = (ECHO,)

    def __init__(self):
        self.calls = 0
        self.list_calls = 0
        self.last_args = None

    async def list_tools(self):
        self.list_calls += 1
        return list(self.tools)

    async def call_tool(self, name, args):
        self.calls += 1
        self.last_args = args
        text = args["text"]
        return NormalizedToolResult(
            text=text, is_error=False, truncated=False, output_bytes=len(text)
        )


class TruncatingShim(Shim):
    async def call_tool(self, name, args):
        self.calls += 1
        return NormalizedToolResult(text="xxxxx", is_error=False, truncated=True, output_bytes=123)


class FailingToolShim(Shim):
    async def call_tool(self, name, args):
        self.calls += 1
        return NormalizedToolResult(
            text="tool said no", is_error=True, truncated=False, output_bytes=12
        )


class DeadBackendShim(Shim):
    async def list_tools(self):
        self.list_calls += 1
        raise ConnectionError("hermes child exited")


class ExplodingShim(Shim):
    async def call_tool(self, name, args):
        raise RuntimeError("boom at /internal/path")


class Ctx:
    def __init__(self, sender="agent1qabcdefghijklmnopqrstuvwxyz0123456789"):
        self.sender = sender
        self.sent = []
        self.fail_send = False

    async def send(self, destination, message):
        if self.fail_send:
            raise RuntimeError("send boom")
        self.sent.append((destination, message))


def cfg(**policy_settings):
    return BridgeConfig(agent={"dev_random_seed": True}, policy=policy_settings)


def audit_events(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


async def call(msg, shim, config, audit, state=None, sender="sender"):
    return await handle_call_tool(sender, msg, shim, config, audit, state=state or PolicyState())


@pytest.mark.asyncio
async def test_denied_call_does_not_invoke_shim(tmp_path):
    s = Shim()
    audit = AuditWriter(tmp_path / "a.jsonl")
    resp = await call(CallTool(tool="echo", args={"text": "x"}), s, cfg(public_tools=[]), audit)
    assert resp.error and s.calls == 0 and audit.count() == 1


@pytest.mark.asyncio
async def test_oversize_args_denied_before_shim(tmp_path):
    s = Shim()
    resp = await call(
        CallTool(tool="echo", args={"text": "xxxx"}),
        s,
        cfg(public_tools=["echo"], max_args_bytes=5),
        AuditWriter(tmp_path / "a.jsonl"),
    )
    assert resp.error == "args exceed max_args_bytes" and s.calls == 0


@pytest.mark.asyncio
async def test_allowed_call_requires_replay_metadata_before_shim(tmp_path):
    s = Shim()
    resp = await call(
        CallTool(tool="echo", args={"text": "ok"}),
        s,
        cfg(public_tools=["echo"]),
        AuditWriter(tmp_path / "a.jsonl"),
    )
    assert resp.error == "missing replay metadata"
    assert s.calls == 0


@pytest.mark.asyncio
async def test_replayed_request_id_is_denied_before_shim(tmp_path):
    s = Shim()
    state = PolicyState()
    c = cfg(public_tools=["echo"])
    audit = AuditWriter(tmp_path / "a.jsonl")
    first = await call(
        CallTool(tool="echo", args=replay_args({"text": "first"}, "req-replay-0001")),
        s,
        c,
        audit,
        state,
    )
    second = await call(
        CallTool(tool="echo", args=replay_args({"text": "changed"}, "req-replay-0001")),
        s,
        c,
        audit,
        state,
    )
    assert first.result == "first"
    assert second.error == "replay detected"
    assert s.calls == 1
    assert s.last_args == {"text": "first"}


@pytest.mark.asyncio
async def test_future_stamped_call_cannot_be_replayed_once_its_receipt_ages(tmp_path, monkeypatch):
    # Stamped 59 s ahead (inside the 60 s skew allowance), the call stays fresh
    # until 359 s after it arrives; a replay at +301 s must still be refused.
    wall_ms = 1_800_000_000_000
    mono = 1_000.0
    monkeypatch.setattr(direct_protocol, "_now_ms", lambda: wall_ms)
    monkeypatch.setattr(policy, "_clock", lambda: mono)
    s = Shim()
    state = PolicyState()
    c = cfg(public_tools=["echo"])
    audit = AuditWriter(tmp_path / "a.jsonl")
    msg = CallTool(
        tool="echo", args=replay_args({"text": "once"}, "req-future-0001", wall_ms + 59_000)
    )
    assert (await call(msg, s, c, audit, state)).result == "once"

    wall_ms += 301_000
    mono += 301.0
    assert (await call(msg, s, c, audit, state)).error == "replay detected"
    assert s.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("issued_at_ms", [float("nan"), float("inf"), float("-inf"), True, "1"])
async def test_non_numeric_replay_timestamps_are_rejected(tmp_path, issued_at_ms):
    s = Shim()
    resp = await call(
        CallTool(tool="echo", args=replay_args({"text": "x"}, "req-nan-00001", issued_at_ms)),
        s,
        cfg(public_tools=["echo"]),
        AuditWriter(tmp_path / "a.jsonl"),
    )
    assert resp.error == "invalid replay metadata"
    assert s.calls == 0


@pytest.mark.asyncio
async def test_stale_replay_metadata_is_denied_before_shim(tmp_path):
    s = Shim()
    stale = replay_args({"text": "old"}, "req-stale-0001", int((time.time() - 3600) * 1000))
    resp = await call(
        CallTool(tool="echo", args=stale),
        s,
        cfg(public_tools=["echo"], replay_ttl_seconds=60),
        AuditWriter(tmp_path / "a.jsonl"),
    )
    assert resp.error == "stale replay metadata"
    assert s.calls == 0


@pytest.mark.asyncio
async def test_calls_without_metadata_are_not_treated_as_replays_when_metadata_is_optional(
    tmp_path,
):
    s = Shim()
    state = PolicyState()
    c = cfg(public_tools=["echo"], require_replay_metadata=False)
    audit = AuditWriter(tmp_path / "a.jsonl")
    for _ in range(2):
        resp = await call(CallTool(tool="echo", args={"text": "same"}), s, c, audit, state)
        assert resp.result == "same"
    assert s.calls == 2


@pytest.mark.asyncio
async def test_arg_validation_failure_denies_before_shim(tmp_path):
    s = Shim()
    resp = await call(
        CallTool(tool="echo", args=replay_args({}, "req-invalid-0001")),
        s,
        cfg(public_tools=["echo"]),
        AuditWriter(tmp_path / "a.jsonl"),
    )
    assert resp.error == "schema validation failed" and s.calls == 0


@pytest.mark.asyncio
async def test_slow_argument_checks_time_out(tmp_path, monkeypatch):
    def slow_validate(tool, args, config):
        time.sleep(0.5)

    monkeypatch.setattr(direct_protocol, "validate_args", slow_validate)
    s = Shim()
    resp = await call(
        CallTool(tool="echo", args=replay_args({"text": "x"}, "req-slow-0001")),
        s,
        BridgeConfig(
            agent={"dev_random_seed": True},
            hermes_mcp={"timeout_seconds": 0.05},
            policy={"public_tools": ["echo"]},
        ),
        AuditWriter(tmp_path / "a.jsonl"),
    )
    assert resp.error == "argument checks timed out" and s.calls == 0


@pytest.mark.asyncio
async def test_schema_validation_error_does_not_leak_raw_args_to_response_or_audit(tmp_path):
    s = Shim()
    raw_value = "sensitive prose that must not be logged"
    resp = await call(
        CallTool(tool="echo", args=replay_args({"text": {"raw": raw_value}}, "req-schema-0001")),
        s,
        cfg(public_tools=["echo"]),
        AuditWriter(tmp_path / "a.jsonl"),
    )
    assert resp.error == "schema validation failed"
    assert raw_value not in (tmp_path / "a.jsonl").read_text(encoding="utf-8")
    assert s.calls == 0


@pytest.mark.asyncio
async def test_schema_validation_error_does_not_leak_raw_property_names(tmp_path):
    s = Shim()
    raw_key = "sensitive prose property name"
    resp = await call(
        CallTool(tool="echo", args=replay_args({raw_key: {"bad": "shape"}}, "req-schema-key-0001")),
        s,
        cfg(public_tools=["echo"]),
        AuditWriter(tmp_path / "a.jsonl"),
    )
    assert resp.error == "schema validation failed"
    assert raw_key not in (tmp_path / "a.jsonl").read_text(encoding="utf-8")
    assert s.calls == 0


@pytest.mark.asyncio
async def test_invalid_schema_request_id_does_not_poison_valid_retry(tmp_path):
    s = Shim()
    state = PolicyState()
    c = cfg(public_tools=["echo"])
    audit = AuditWriter(tmp_path / "a.jsonl")
    invalid = await call(
        CallTool(tool="echo", args=replay_args({"text": {"bad": "shape"}}, "req-retry-0001")),
        s,
        c,
        audit,
        state,
    )
    retry = await call(
        CallTool(tool="echo", args=replay_args({"text": "fixed"}, "req-retry-0001")),
        s,
        c,
        audit,
        state,
    )
    assert invalid.error == "schema validation failed"
    assert retry.result == "fixed"
    assert s.calls == 1


@pytest.mark.asyncio
async def test_invalid_call_consumes_rate_before_validation(tmp_path):
    s = Shim()
    state = PolicyState()
    c = cfg(public_tools=["echo"], max_calls_per_minute_per_sender=1)
    audit = AuditWriter(tmp_path / "a.jsonl")
    invalid = await call(CallTool(tool="bad\nname", args={"text": "x"}), s, c, audit, state)
    assert invalid.error == "unsafe tool name"
    denied = await call(
        CallTool(tool="echo", args=replay_args({"text": "ok"}, "req-rate-0001")), s, c, audit, state
    )
    assert denied.error == "rate limit exceeded"
    assert s.calls == 0


@pytest.mark.asyncio
async def test_hostile_tool_names_keep_the_audit_log_valid_and_bounded(tmp_path):
    audit = AuditWriter(tmp_path / "a.jsonl")
    state = PolicyState()
    c = cfg(public_tools=["echo"])
    too_long = await call(CallTool(tool="a-" * 500_000, args={}), Shim(), c, audit, state)
    assert too_long.error == "tool name too long"
    shaped = await call(CallTool(tool="x tok" + "en=", args={}), Shim(), c, audit, state)
    assert shaped.error == "unsafe tool name"
    events = audit_events(tmp_path / "a.jsonl")  # every line is valid JSON
    assert len(events) == 2
    assert len(events[0]["tool"]) <= MAX_TOOL_NAME_LENGTH + 1


@pytest.mark.asyncio
async def test_unsafe_backend_tool_names_do_not_break_other_calls(tmp_path):
    class MixedShim(Shim):
        tools = (ECHO, {"name": "github/search", "inputSchema": {"type": "object"}})

    s = MixedShim()
    resp = await call(
        CallTool(tool="echo", args=replay_args({"text": "fine"}, "req-mixed-0001")),
        s,
        cfg(public_tools=["echo"]),
        AuditWriter(tmp_path / "a.jsonl"),
    )
    assert resp.result == "fine"


@pytest.mark.asyncio
async def test_tool_errors_are_returned_as_error_only(tmp_path):
    resp = await call(
        CallTool(tool="echo", args=replay_args({"text": "x"}, "req-toolerr-0001")),
        FailingToolShim(),
        cfg(public_tools=["echo"]),
        AuditWriter(tmp_path / "a.jsonl"),
    )
    assert resp.result is None and resp.error == "tool said no"


@pytest.mark.asyncio
async def test_unknown_sender_list_tools_public_only(tmp_path):
    resp = await handle_list_tools(
        "sender",
        Shim(),
        cfg(public_tools=["echo"]),
        AuditWriter(tmp_path / "a.jsonl"),
        state=PolicyState(),
    )
    assert [t["name"] for t in resp.tools] == ["echo"]


@pytest.mark.asyncio
async def test_list_tools_response_size_cap(tmp_path):
    resp = await handle_list_tools(
        "sender",
        Shim(),
        cfg(public_tools=["echo"], max_list_tools_response_bytes=1),
        AuditWriter(tmp_path / "a.jsonl"),
        state=PolicyState(),
    )
    assert resp.tools == [] and resp.error == "response too large"


@pytest.mark.asyncio
async def test_list_tools_rate_limit_denies_before_shim(tmp_path):
    s = Shim()
    state = PolicyState()
    c = cfg(public_tools=["echo"], max_list_tools_per_minute_per_sender=1)
    audit = AuditWriter(tmp_path / "a.jsonl")
    assert (await handle_list_tools("rate_sender", s, c, audit, state=state)).tools
    denied = await handle_list_tools("rate_sender", s, c, audit, state=state)
    assert denied.error == "rate limit exceeded"
    assert s.list_calls == 1


@pytest.mark.asyncio
async def test_call_is_audited_before_a_failed_send(tmp_path):
    audit_path = tmp_path / "a.jsonl"
    proto = build_protocol(Shim(), cfg(public_tools=["echo"]), AuditWriter(audit_path))
    call_handler = proto.signed_message_handlers[Model.build_schema_digest(CallTool)]
    ctx = Ctx()
    ctx.fail_send = True
    msg = CallTool(tool="echo", args=replay_args({"text": "ok"}, "req-audit-0001"))
    with pytest.raises(RuntimeError, match="send boom"):
        await call_handler(ctx, ctx.sender, msg)
    events = audit_events(audit_path)
    assert [e.get("send_status") for e in events] == ["before_send", "failure"]
    assert events[0]["decision"] == "allowed"


@pytest.mark.asyncio
async def test_call_tool_audit_uses_normalized_truncation_metadata(tmp_path):
    resp = await call(
        CallTool(tool="echo", args=replay_args({"text": "ok"}, "req-trunc-0001")),
        TruncatingShim(),
        cfg(public_tools=["echo"]),
        AuditWriter(tmp_path / "a.jsonl"),
    )
    assert resp.result == "xxxxx"
    event = audit_events(tmp_path / "a.jsonl")[0]
    assert event["output_bytes"] == 123
    assert event["truncated"] is True


@pytest.mark.asyncio
async def test_build_protocol_audits_send_success_and_failure(tmp_path):
    audit_path = tmp_path / "a.jsonl"
    proto = build_protocol(Shim(), cfg(public_tools=["echo"]), AuditWriter(audit_path))
    list_handler = proto.signed_message_handlers[Model.build_schema_digest(ListTools())]

    ok_ctx = Ctx()
    await list_handler(ok_ctx, ok_ctx.sender, ListTools())
    assert ok_ctx.sent

    fail_ctx = Ctx()
    fail_ctx.fail_send = True
    with pytest.raises(RuntimeError):
        await list_handler(fail_ctx, fail_ctx.sender, ListTools())

    statuses = [e.get("send_status") for e in audit_events(audit_path)]
    assert "success" in statuses and "failure" in statuses


@pytest.mark.asyncio
async def test_each_protocol_has_its_own_rate_limit_state(tmp_path):
    c = cfg(public_tools=["echo"], max_list_tools_per_minute_per_sender=1)
    digest = Model.build_schema_digest(ListTools())
    for _ in range(2):
        proto = build_protocol(Shim(), c, AuditWriter(tmp_path / "a.jsonl"))
        ctx = Ctx()
        await proto.signed_message_handlers[digest](ctx, ctx.sender, ListTools())
        assert ctx.sent[0][1].error is None


@pytest.mark.asyncio
async def test_direct_protocol_audit_redacts_long_sender(tmp_path):
    sender = "agent1qabcdefghijklmnopqrstuvwxyz0123456789abcdefghijklmnopqrstuvwxyz"
    await call(
        CallTool(tool="echo", args=replay_args({"text": "ok"}, "req-redact-0001")),
        Shim(),
        cfg(public_tools=["echo"]),
        AuditWriter(tmp_path / "a.jsonl"),
        sender=sender,
    )
    text = (tmp_path / "a.jsonl").read_text(encoding="utf-8")
    assert sender not in text
    assert "…" in text


@pytest.mark.asyncio
async def test_list_tools_reports_backend_unavailable(tmp_path):
    resp = await handle_list_tools(
        "dead_backend_lister",
        DeadBackendShim(),
        cfg(public_tools=["echo"]),
        AuditWriter(tmp_path / "a.jsonl"),
        state=PolicyState(),
    )
    assert resp.tools == [] and resp.error == "backend unavailable"
    event = audit_events(tmp_path / "a.jsonl")[-1]
    assert event["decision"] == "error"
    assert event["error_class"] == "ConnectionError"


@pytest.mark.asyncio
async def test_call_tool_reports_backend_unavailable_without_invoking(tmp_path):
    s = DeadBackendShim()
    resp = await call(
        CallTool(tool="echo", args=replay_args({"text": "x"}, request_id="dead-backend-0001")),
        s,
        cfg(public_tools=["echo"]),
        AuditWriter(tmp_path / "a.jsonl"),
    )
    assert resp.error == "backend unavailable" and s.calls == 0


@pytest.mark.asyncio
async def test_internal_error_stays_generic_for_remote_caller(tmp_path):
    resp = await call(
        CallTool(tool="echo", args=replay_args({"text": "x"}, request_id="exploding-0001")),
        ExplodingShim(),
        cfg(public_tools=["echo"]),
        AuditWriter(tmp_path / "a.jsonl"),
    )
    assert resp.error == "internal bridge error"
    assert "/internal/path" not in resp.model_dump_json()
