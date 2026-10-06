from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import time
import uuid
from typing import Any

from uagents import Context, Protocol
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
from .mcp_shim import ToolBackend
from .policy import (
    PolicyState,
    authorize,
    consume_call_rate,
    consume_list_tools_rate,
    replay_retention_seconds,
    visible_tools,
)
from .seller import PaymentProof
from .services import ServiceDesk
from .tool_names import audit_tool_name, validate_tool_name

_REPLAY_META_KEY = "_hermes_fetch_ai"
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")
_ALLOWED_REPLAY_META_KEYS = {"request_id", "issued_at_ms", "payment"}
_MAX_PROOF_CHARS = 128
BACKEND_UNAVAILABLE = "backend unavailable"

logger = get_logger("hermes_fetch_ai")


def _now_ms() -> int:
    return int(time.time() * 1000)


def replay_args(
    args: dict[str, Any],
    request_id: str | None = None,
    *,
    payment: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return tool args with the bridge's replay-protection metadata attached.

    The uAgents MCP `CallTool` model has only `tool` and `args`, so v1 carries
    bridge metadata under a reserved args key. The bridge strips this key before
    JSON-schema validation and before invoking the Hermes tool. A paid call
    adds ``payment={"reference": ..., "tx_hash": ...}``.
    """
    meta: dict[str, Any] = {
        "request_id": request_id or str(uuid.uuid4()),
        "issued_at_ms": _now_ms(),
    }
    if payment is not None:
        meta["payment"] = payment
    return {**args, _REPLAY_META_KEY: meta}


def _payment_proof(meta: dict[str, Any]) -> PaymentProof | None:
    payment = meta.get("payment")
    if payment is None:
        return None
    if (
        not isinstance(payment, dict)
        or set(payment) != {"reference", "tx_hash"}
        or not all(
            isinstance(value, str) and 0 < len(value) <= _MAX_PROOF_CHARS
            for value in payment.values()
        )
    ):
        raise ValueError("invalid payment proof")
    return PaymentProof(reference=payment["reference"], tx_hash=payment["tx_hash"])


def _split_replay_metadata(
    sender: str, args: dict[str, Any], cfg: BridgeConfig
) -> tuple[dict[str, Any], str | None, PaymentProof | None]:
    """Return the tool's own args, the call's replay fingerprint, and any payment proof.

    The fingerprint is None when the call has no replay metadata, which is only
    allowed with ``require_replay_metadata: false``. Such calls cannot be told
    apart from deliberate repeats, so they get no replay protection, and
    cannot carry a payment.
    """
    if not isinstance(args, dict):
        raise TypeError("tool args must be an object")

    clean_args = dict(args)
    meta = clean_args.pop(_REPLAY_META_KEY, None)
    if meta is None:
        if cfg.policy.require_replay_metadata:
            raise ValueError("missing replay metadata")
        return clean_args, None, None

    if not isinstance(meta, dict) or set(meta) - _ALLOWED_REPLAY_META_KEYS:
        raise ValueError("invalid replay metadata")
    request_id = meta.get("request_id")
    if not isinstance(request_id, str) or not _REQUEST_ID_RE.fullmatch(request_id):
        raise ValueError("invalid replay metadata")
    issued_at_ms = meta.get("issued_at_ms")
    if (
        isinstance(issued_at_ms, bool)
        or not isinstance(issued_at_ms, int | float)
        or not math.isfinite(issued_at_ms)
    ):
        raise ValueError("invalid replay metadata")
    age_ms = _now_ms() - int(issued_at_ms)
    if age_ms > cfg.policy.replay_ttl_seconds * 1000:
        raise ValueError("stale replay metadata")
    if -age_ms > cfg.policy.max_replay_clock_skew_seconds * 1000:
        raise ValueError("future replay metadata")

    proof = _payment_proof(meta)
    material = json.dumps({"sender": sender, "request_id": request_id}, sort_keys=True)
    return clean_args, hashlib.sha256(material.encode("utf-8")).hexdigest(), proof


async def handle_list_tools(
    sender: str,
    shim: ToolBackend,
    cfg: BridgeConfig,
    audit: AuditWriter,
    *,
    state: PolicyState,
    desk: ServiceDesk | None = None,
) -> ListToolsResponse:
    trace_id = str(uuid.uuid4())
    start = time.perf_counter()
    ok, reason = consume_list_tools_rate(sender, cfg.policy, state)
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
    filtered = visible_tools(sender, tools, cfg.policy)
    if desk is not None:
        filtered += desk.tools(sender)
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
    sender: str,
    msg: CallTool,
    shim: ToolBackend,
    cfg: BridgeConfig,
    audit: AuditWriter,
    *,
    state: PolicyState,
    desk: ServiceDesk | None = None,
) -> CallToolResponse:
    trace_id = str(uuid.uuid4())
    start = time.perf_counter()
    args_bytes = len(json.dumps(msg.args, sort_keys=True).encode("utf-8"))
    decision = "denied"
    reason = ""
    output_bytes = 0
    truncated = False
    extra: dict[str, Any] = {}
    try:
        ok, reason = consume_call_rate(sender, cfg.policy, state)
        if not ok:
            return CallToolResponse(result=None, error=reason)
        try:
            tool_name = validate_tool_name(msg.tool)
        except ValueError as exc:
            reason = str(exc)
            return CallToolResponse(result=None, error=reason)
        if args_bytes > cfg.policy.max_args_bytes:
            reason = "args exceed max_args_bytes"
            return CallToolResponse(result=None, error=reason)
        if desk is not None and desk.has(tool_name):
            # Services are offered to every sender (paid ones after payment);
            # the denylist still wins.
            if tool_name in cfg.policy.denied_tools:
                reason = "tool denied"
                return CallToolResponse(result=None, error=reason)
            try:
                clean_args, fingerprint, proof = _split_replay_metadata(sender, msg.args, cfg)
            except (TypeError, ValueError) as exc:
                reason = str(exc)
                return CallToolResponse(result=None, error=reason)

            def remember() -> tuple[bool, str]:
                if fingerprint is None:
                    return True, "ok"
                return state.replays.remember(
                    fingerprint,
                    replay_retention_seconds(cfg.policy),
                    cfg.policy.max_replay_entries,
                )

            outcome = await desk.call(
                sender=sender,
                tool_name=tool_name,
                args=clean_args,
                proof=proof,
                remember_replay=remember,
            )
            decision, reason = outcome.decision, outcome.reason
            output_bytes, truncated, extra = outcome.output_bytes, outcome.truncated, outcome.audit
            if outcome.is_error:
                return CallToolResponse(result=None, error=outcome.text)
            return CallToolResponse(result=outcome.text, error=None)
        ok, reason = authorize(sender, tool_name, cfg.policy)
        if not ok:
            return CallToolResponse(result=None, error=reason)
        try:
            clean_args, replay_fingerprint, _ = _split_replay_metadata(sender, msg.args, cfg)
        except (TypeError, ValueError) as exc:
            reason = str(exc)
            return CallToolResponse(result=None, error=reason)
        try:
            inventory = await shim.list_tools()
        except Exception as exc:  # noqa: BLE001 - see handle_list_tools
            logger.error(
                "Hermes MCP backend unavailable for call_tool (%s)", exc.__class__.__name__
            )
            decision = "error"
            reason = BACKEND_UNAVAILABLE
            return CallToolResponse(result=None, error=reason)
        found = next((t for t in inventory if t.get("name") == tool_name), None)
        if found is None:
            reason = "unknown tool"
            return CallToolResponse(result=None, error=reason)
        try:
            # URL checks resolve DNS, so keep them off the event loop, and bound them.
            await asyncio.wait_for(
                asyncio.to_thread(validate_args, found, clean_args, cfg),
                timeout=cfg.hermes_mcp.timeout_seconds,
            )
        except TimeoutError:
            reason = "argument checks timed out"
            return CallToolResponse(result=None, error=reason)
        except (TypeError, ValueError) as exc:
            reason = str(exc)
            return CallToolResponse(result=None, error=reason)
        if replay_fingerprint is not None:
            ok, reason = state.replays.remember(
                replay_fingerprint,
                replay_retention_seconds(cfg.policy),
                cfg.policy.max_replay_entries,
            )
            if not ok:
                return CallToolResponse(result=None, error=reason)
        normalized = await shim.call_tool(tool_name, clean_args)
        decision = "error" if normalized.is_error else "allowed"
        reason = "tool error" if normalized.is_error else "ok"
        output_bytes = normalized.output_bytes
        truncated = normalized.truncated
        if normalized.is_error:
            return CallToolResponse(result=None, error=normalized.text)
        return CallToolResponse(result=normalized.text, error=None)
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
            tool=audit_tool_name(getattr(msg, "tool", None)),
            decision=decision,
            reason=reason,
            duration_ms=int((time.perf_counter() - start) * 1000),
            args_bytes=args_bytes,
            output_bytes=output_bytes,
            truncated=truncated,
            mode=cfg.hermes_mcp.mode,
            send_status="before_send",
            **extra,
        )


async def _send_with_audit(
    ctx: Context,
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
    shim: ToolBackend, cfg: BridgeConfig, audit: AuditWriter, desk: ServiceDesk | None = None
) -> Protocol:
    """The bridge's MCP protocol, with its own rate-limit and replay state."""
    proto = Protocol(spec=mcp_protocol_spec, role="server")
    state = PolicyState()

    @proto.on_message(model=ListTools)
    async def _list(ctx: Context, sender: str, msg: ListTools) -> None:
        resp = await handle_list_tools(sender, shim, cfg, audit, state=state, desk=desk)
        await _send_with_audit(ctx, sender, resp, audit, cfg, "list_tools")

    @proto.on_message(model=CallTool)
    async def _call(ctx: Context, sender: str, msg: CallTool) -> None:
        resp = await handle_call_tool(sender, msg, shim, cfg, audit, state=state, desk=desk)
        await _send_with_audit(
            ctx, sender, resp, audit, cfg, "call_tool", audit_tool_name(msg.tool)
        )

    return proto
