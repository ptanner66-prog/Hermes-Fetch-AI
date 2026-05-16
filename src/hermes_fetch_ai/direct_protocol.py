from __future__ import annotations

import hashlib
import json
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
from .policy import authorize, authorize_list_tools, normalize_tool_name, visible_tools


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


def _tool_fingerprint(tool: dict[str, Any]) -> str:
    material = {
        "name": tool.get("name"),
        "description": tool.get("description", ""),
        "inputSchema": tool.get("inputSchema") or {"type": "object", "properties": {}},
    }
    raw = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


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

    tools = await shim.list_tools()
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
    ctx: Any, sender: str, msg: CallTool, shim: Any, cfg: BridgeConfig, audit: AuditWriter
) -> CallToolResponse:
    trace_id = str(uuid.uuid4())
    start = time.perf_counter()
    args_bytes = len(json.dumps(msg.args, sort_keys=True).encode("utf-8"))
    decision = "denied"
    reason = ""
    result = None
    try:
        try:
            tool_name = normalize_tool_name(msg.tool)
        except ValueError as exc:
            reason = str(exc)
            return CallToolResponse(result=None, error=reason)
        if args_bytes > cfg.policy.max_args_bytes:
            reason = "args exceed max_args_bytes"
            return CallToolResponse(result=None, error=reason)
        ok, reason = authorize(sender, tool_name, msg.args, "mcp", cfg.policy)
        if not ok:
            return CallToolResponse(result=None, error=reason)
        tools = [_tool_dict(t) for t in await shim.list_tools()]
        found = next((t for t in tools if t.get("name") == tool_name), None)
        if not found:
            reason = "unknown tool"
            return CallToolResponse(result=None, error=reason)
        before_fp = _tool_fingerprint(found)
        validate_args(found, msg.args, cfg)
        # The descriptor/schema fingerprint is computed immediately before the
        # call after the fresh inventory lookup. This makes validation and the
        # invocation use the same checked descriptor rather than stale policy data.
        if before_fp != _tool_fingerprint(found):
            reason = "tool descriptor changed before call"
            return CallToolResponse(result=None, error=reason)
        normalized = await shim.call_tool(tool_name, msg.args)
        decision = "error" if normalized.is_error else "allowed"
        reason = "tool error" if normalized.is_error else "ok"
        result = normalized.text
        return CallToolResponse(
            result=normalized.text, error=normalized.text if normalized.is_error else None
        )
    except Exception as e:
        reason = str(e)
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
            output_bytes=len((result or "").encode()),
            truncated=False,
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
            reason=str(exc),
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
