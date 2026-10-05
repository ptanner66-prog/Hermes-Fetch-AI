from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
import uuid
from typing import Any

from uagents import Protocol
from uagents_adapter.mcp.protocol import (
    CallTool,
    CallToolResponse,
    ListTools,
    ListToolsResponse,
    mcp_protocol_spec,
)

from .arg_validator import validate_args
from .audit import AuditWriter
from .config import BridgeConfig
from .logging import get_logger
from .policy import (
    REPLAYS,
    ReplayCache,
    authorize,
    authorize_list_tools,
    consume_call_rate,
    normalize_tool_name,
    visible_tools,
)

_REPLAY_META_KEY = "_hermes_fetch_ai"
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")
_ALLOWED_REPLAY_META_KEYS = {"request_id", "issued_at_ms"}
BACKEND_UNAVAILABLE = "backend unavailable"

logger = get_logger("hermes_fetch_ai")


def _sender(ctx: Any) -> str:
    return str(getattr(ctx, "sender", None) or getattr(ctx, "message_sender", None) or "unknown")


def _tool_dict(tool: Any) -> dict[str, Any]:
    if isinstance(tool, dict):
        d = dict(tool)
    else:
        dump = getattr(tool, "model_dump", None)
        if callable(dump):
            d = dump(by_alias=True, exclude_none=True)
        else:
            d = {
                "name": getattr(tool, "name", ""),
                "description": getattr(tool, "description", ""),
                "inputSchema": getattr(tool, "inputSchema", None),
            }
    d["name"] = normalize_tool_name(str(d.get("name", "")))
    d["inputSchema"] = d.get("inputSchema") or {"type": "object", "properties": {}}
    return d


def replay_args(args: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    """Return tool args with bridge-level replay/idempotency metadata attached.

    The uAgents MCP `CallTool` model has only `tool` and `args`, so v1 carries
    bridge metadata under a reserved args key. The bridge strips this key before
    JSON-schema validation and before invoking the Hermes tool.
    """

    return {
        **args,
        _REPLAY_META_KEY: {
            "request_id": request_id or str(uuid.uuid4()),
            "issued_at_ms": int(time.time() * 1000),
        },
    }


def _clean_args_and_replay_fingerprint(
    sender: str, tool_name: str, args: dict[str, Any], cfg: BridgeConfig
) -> tuple[dict[str, Any], str]:
    if not isinstance(args, dict):
        raise TypeError("tool args must be an object")

    clean_args = dict(args)
    meta = clean_args.pop(_REPLAY_META_KEY, None)
    request_id: str | None = None

    if meta is None:
        if cfg.policy.require_replay_metadata:
            raise ValueError("missing replay metadata")
    else:
        if not isinstance(meta, dict):
            raise ValueError("invalid replay metadata")
        if set(meta) - _ALLOWED_REPLAY_META_KEYS:
            raise ValueError("invalid replay metadata")
        raw_request_id = meta.get("request_id")
        if not isinstance(raw_request_id, str) or not _REQUEST_ID_RE.fullmatch(raw_request_id):
            raise ValueError("invalid replay metadata")
        request_id = raw_request_id
        raw_issued_at_ms = meta.get("issued_at_ms")
        if isinstance(raw_issued_at_ms, bool) or not isinstance(raw_issued_at_ms, int | float):
            raise ValueError("invalid replay metadata")
        issued_at_ms = int(raw_issued_at_ms)
        now_ms = int(time.time() * 1000)
        age_ms = now_ms - issued_at_ms
        if age_ms > int(cfg.policy.replay_ttl_seconds * 1000):
            raise ValueError("stale replay metadata")
        if -age_ms > int(cfg.policy.max_replay_clock_skew_seconds * 1000):
            raise ValueError("future replay metadata")

    material: dict[str, Any]
    if request_id is not None:
        material = {"sender": sender, "request_id": request_id}
    else:
        material = {"sender": sender, "tool": tool_name, "args": clean_args}
    raw = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return clean_args, hashlib.sha256(raw).hexdigest()


async def handle_list_tools(
    ctx: Any, sender: str, shim: Any, cfg: BridgeConfig, audit: AuditWriter
) -> ListToolsResponse:
    trace_id = str(uuid.uuid4())
    start = time.perf_counter()
    ok, reason = authorize_list_tools(sender, cfg.policy)
    if not ok:
        audit.write(
            trace_id=trace_id,
            sender=sender,
            protocol="mcp",
            msg_type="list_tools",
            decision="denied",
            reason=reason,
            duration_ms=int((time.perf_counter() - start) * 1000),
            output_bytes=0,
            truncated=False,
            mode=cfg.hermes_mcp.mode,
        )
        return ListToolsResponse(tools=[], error=reason)

    # Any backend failure is reported to the caller as "backend unavailable".
    try:
        tools = await shim.list_tools()
    except Exception as exc:  # noqa: BLE001
        logger.error("Hermes MCP backend unavailable for list_tools (%s)", exc.__class__.__name__)
        audit.write(
            trace_id=trace_id,
            sender=sender,
            protocol="mcp",
            msg_type="list_tools",
            decision="error",
            reason=BACKEND_UNAVAILABLE,
            duration_ms=int((time.perf_counter() - start) * 1000),
            error_class=exc.__class__.__name__,
            output_bytes=0,
            truncated=False,
            mode=cfg.hermes_mcp.mode,
        )
        return ListToolsResponse(tools=[], error=BACKEND_UNAVAILABLE)
    filtered = [_tool_dict(t) for t in visible_tools(sender, tools, cfg.policy)]
    raw = json.dumps(filtered).encode("utf-8")
    truncated = False
    reason = "ok"
    if len(raw) > cfg.policy.max_list_tools_response_bytes:
        filtered = []
        truncated = True
        reason = "response too large"
    audit.write(
        trace_id=trace_id,
        sender=sender,
        protocol="mcp",
        msg_type="list_tools",
        decision="allowed",
        reason=reason,
        duration_ms=int((time.perf_counter() - start) * 1000),
        output_bytes=len(raw),
        truncated=truncated,
        mode=cfg.hermes_mcp.mode,
    )
    return ListToolsResponse(tools=filtered, error="response too large" if truncated else None)


async def handle_call_tool(
    ctx: Any,
    sender: str,
    msg: CallTool,
    shim: Any,
    cfg: BridgeConfig,
    audit: AuditWriter,
    *,
    replay_cache: ReplayCache = REPLAYS,
) -> CallToolResponse:
    trace_id = str(uuid.uuid4())
    start = time.perf_counter()
    args_bytes = len(json.dumps(msg.args, sort_keys=True).encode("utf-8"))
    decision = "denied"
    reason = ""
    output_bytes = 0
    truncated = False
    try:
        ok, reason = consume_call_rate(sender, cfg.policy)
        if not ok:
            return CallToolResponse(result=None, error=reason)
        try:
            tool_name = normalize_tool_name(msg.tool)
        except ValueError as exc:
            reason = str(exc)
            return CallToolResponse(result=None, error=reason)
        if args_bytes > cfg.policy.max_args_bytes:
            reason = "args exceed max_args_bytes"
            return CallToolResponse(result=None, error=reason)
        ok, reason = authorize(sender, tool_name, msg.args, "mcp", cfg.policy, consume_rate=False)
        if not ok:
            return CallToolResponse(result=None, error=reason)
        try:
            clean_args, replay_fingerprint = _clean_args_and_replay_fingerprint(
                sender, tool_name, msg.args, cfg
            )
        except (TypeError, ValueError) as exc:
            reason = str(exc)
            return CallToolResponse(result=None, error=reason)
        try:
            inventory = await shim.list_tools()
        except Exception as exc:  # noqa: BLE001 - see handle_list_tools
            logger.error("Hermes MCP backend unavailable for call_tool (%s)", exc.__class__.__name__)
            decision = "error"
            reason = BACKEND_UNAVAILABLE
            return CallToolResponse(result=None, error=reason)
        tools = [_tool_dict(t) for t in inventory]
        found = next((t for t in tools if t.get("name") == tool_name), None)
        if not found:
            reason = "unknown tool"
            return CallToolResponse(result=None, error=reason)
        try:
            # URL checks resolve DNS, so keep them off the event loop.
            await asyncio.to_thread(validate_args, found, clean_args, cfg)
        except (TypeError, ValueError) as exc:
            reason = str(exc)
            return CallToolResponse(result=None, error=reason)
        ok, reason = replay_cache.allow(
            replay_fingerprint, cfg.policy.replay_ttl_seconds, cfg.policy.max_replay_entries
        )
        if not ok:
            return CallToolResponse(result=None, error=reason)
        normalized = await shim.call_tool(tool_name, clean_args)
        decision = "error" if normalized.is_error else "allowed"
        reason = "tool error" if normalized.is_error else "ok"
        output_bytes = normalized.output_bytes
        truncated = normalized.truncated
        return CallToolResponse(
            result=normalized.text, error=normalized.text if normalized.is_error else None
        )
    except Exception:
        # Never leak internals to the remote caller; keep the traceback for the operator.
        logger.exception("internal bridge error handling call_tool (trace_id=%s)", trace_id)
        decision = "error"
        reason = "internal bridge error"
        return CallToolResponse(result=None, error=reason)
    finally:
        audit.write(
            trace_id=trace_id,
            sender=sender,
            protocol="mcp",
            msg_type="call_tool",
            tool=getattr(msg, "tool", None),
            decision=decision,
            reason=reason,
            duration_ms=int((time.perf_counter() - start) * 1000),
            args_bytes=args_bytes,
            output_bytes=output_bytes,
            truncated=truncated,
            mode=cfg.hermes_mcp.mode,
            send_status="before_send",
        )


async def _send_with_audit(
    ctx: Any,
    sender: str,
    response: Any,
    audit: AuditWriter,
    cfg: BridgeConfig,
    msg_type: str,
    tool: str | None = None,
) -> None:
    trace_id = str(uuid.uuid4())
    start = time.perf_counter()
    try:
        await ctx.send(sender, response)
    except Exception as exc:
        audit.write(
            trace_id=trace_id,
            sender=sender,
            protocol="mcp",
            msg_type=msg_type,
            tool=tool,
            decision="send",
            reason="send failed",
            duration_ms=int((time.perf_counter() - start) * 1000),
            error_class=exc.__class__.__name__,
            mode=cfg.hermes_mcp.mode,
            send_status="failure",
        )
        raise
    audit.write(
        trace_id=trace_id,
        sender=sender,
        protocol="mcp",
        msg_type=msg_type,
        tool=tool,
        decision="send",
        reason="ok",
        duration_ms=int((time.perf_counter() - start) * 1000),
        mode=cfg.hermes_mcp.mode,
        send_status="success",
    )


def build_protocol(
    shim: Any, cfg: BridgeConfig, audit: AuditWriter, logger: Any = None
) -> Protocol:
    proto = Protocol(spec=mcp_protocol_spec, role="server")

    @proto.on_message(model=ListTools)
    async def _list(ctx: Any, sender_or_msg: Any, maybe_msg: ListTools | None = None) -> None:
        sender = str(sender_or_msg) if maybe_msg is not None else _sender(ctx)
        resp = await handle_list_tools(ctx, sender, shim, cfg, audit)
        await _send_with_audit(ctx, sender, resp, audit, cfg, "list_tools")

    @proto.on_message(model=CallTool)
    async def _call(ctx: Any, sender_or_msg: Any, maybe_msg: CallTool | None = None) -> None:
        sender = str(sender_or_msg) if maybe_msg is not None else _sender(ctx)
        msg = maybe_msg if maybe_msg is not None else sender_or_msg
        resp = await handle_call_tool(ctx, sender, msg, shim, cfg, audit)
        await _send_with_audit(ctx, sender, resp, audit, cfg, "call_tool", msg.tool)

    return proto
