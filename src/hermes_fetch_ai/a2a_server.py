from __future__ import annotations

import asyncio
import hmac
import json
import os
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlparse

from uagents_adapter.mcp.protocol import CallTool

from ._redaction import redact_text
from .audit import AuditWriter
from .config import BridgeConfig
from .direct_protocol import handle_call_tool, handle_list_tools
from .mcp_shim import HermesMCPClientShim

A2A_PROTOCOL_VERSION = "0.3.0"
JSONRPC_VERSION = "2.0"
REMOTE_A2A_ERROR = "A2A request failed"

JSONRPC_INVALID_REQUEST = -32600
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602
JSONRPC_INTERNAL_ERROR = -32603


def _base_url(cfg: BridgeConfig) -> str:
    if cfg.a2a.public_base_url:
        return cfg.a2a.public_base_url.rstrip("/")
    if cfg.agent.endpoint:
        return cfg.agent.endpoint.rstrip("/")
    return f"http://{cfg.a2a.host}:{cfg.a2a.port}"


def _a2a_rpc_url(cfg: BridgeConfig) -> str:
    return _base_url(cfg) + cfg.a2a.rpc_path


def build_agent_card(cfg: BridgeConfig) -> dict[str, Any]:
    """Build a public A2A Agent Card without secrets or internal tool descriptors."""

    return {
        "protocolVersion": A2A_PROTOCOL_VERSION,
        "name": cfg.agent.name,
        "description": cfg.agent.description,
        "url": _a2a_rpc_url(cfg),
        "preferredTransport": "JSONRPC",
        "version": "0.1.0",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False,
        },
        "supportedInterfaces": [
            {
                "url": _a2a_rpc_url(cfg),
                "protocolBinding": "JSONRPC",
                "protocolVersion": A2A_PROTOCOL_VERSION,
            }
        ],
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "skills": [
            {
                "id": "hermes-policy-gated-tools",
                "name": "Hermes policy-gated tool bridge",
                "description": (
                    "Routes structured A2A requests to an allowlisted Hermes tool surface "
                    "after policy, argument, redaction, and audit checks."
                ),
                "tags": ["hermes", "fetch-ai", "uagents", "a2a", "mcp"],
                "examples": [
                    "Send a data part with operation=list_tools",
                    "Send a data part with operation=call_tool, tool=<name>, args=<object>",
                ],
                "inputModes": ["application/json"],
                "outputModes": ["application/json"],
            }
        ],
        "metadata": {
            "bridge": "hermes-fetch-ai",
            "toolExposure": "policy-gated",
            "chatProtocol": "out-of-scope",
        },
    }


def _jsonrpc_success(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _extract_sender(params: dict[str, Any]) -> str:
    raw_message = params.get("message")
    message: dict[str, Any] = raw_message if isinstance(raw_message, dict) else {}
    raw_metadata = params.get("metadata")
    metadata: dict[str, Any] = raw_metadata if isinstance(raw_metadata, dict) else {}
    raw_message_metadata = message.get("metadata")
    message_metadata: dict[str, Any] = (
        raw_message_metadata if isinstance(raw_message_metadata, dict) else {}
    )
    sender = (
        metadata.get("sender")
        or metadata.get("from")
        or message_metadata.get("sender")
        or message_metadata.get("from")
        or "a2a:anonymous"
    )
    return str(sender)


def _extract_operation(params: dict[str, Any]) -> dict[str, Any]:
    message = params.get("message")
    if not isinstance(message, dict):
        raise ValueError("message object is required")
    parts = message.get("parts")
    if not isinstance(parts, list):
        raise ValueError("message.parts array is required")
    for part in parts:
        if not isinstance(part, dict):
            continue
        data = part.get("data")
        if part.get("kind") == "data" and isinstance(data, dict):
            operation = data.get("operation")
            if operation in {"list_tools", "call_tool"}:
                return data
    raise ValueError("A2A bridge requires a data part with operation=list_tools or call_tool")


def _message_result(data: dict[str, Any], context_id: str) -> dict[str, Any]:
    return {
        "kind": "message",
        "messageId": str(uuid.uuid4()),
        "contextId": context_id,
        "role": "agent",
        "parts": [{"kind": "data", "data": data}],
        "metadata": {"bridge": "hermes-fetch-ai"},
    }


def _completed_task(
    request_message: dict[str, Any], data: dict[str, Any], operation: str, context_id: str | None
) -> dict[str, Any]:
    task_id = str(uuid.uuid4())
    ctx_id = context_id or str(uuid.uuid4())
    history = [dict(request_message, taskId=task_id, contextId=ctx_id)]
    return {
        "id": task_id,
        "contextId": ctx_id,
        "kind": "task",
        "status": {"state": "completed"},
        "artifacts": [
            {
                "artifactId": str(uuid.uuid4()),
                "name": operation,
                "parts": [{"kind": "data", "data": data}],
            }
        ],
        "history": history,
        "metadata": {"bridge": "hermes-fetch-ai", "operation": operation},
    }


class A2ABridge:
    def __init__(
        self,
        cfg: BridgeConfig,
        shim_factory: Callable[[BridgeConfig], Any] | None = None,
        audit: AuditWriter | None = None,
    ) -> None:
        self.cfg = cfg
        self.shim_factory = shim_factory or HermesMCPClientShim
        self.audit = audit or AuditWriter(cfg.audit_path)
        self.tasks: dict[str, dict[str, Any]] = {}
        self._tasks_lock = threading.Lock()

    async def handle_jsonrpc(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_id = payload.get("id")
        if payload.get("jsonrpc") != JSONRPC_VERSION or not isinstance(payload.get("method"), str):
            return _jsonrpc_error(request_id, JSONRPC_INVALID_REQUEST, "invalid JSON-RPC request")
        method = payload["method"]
        raw_params = payload.get("params")
        if raw_params is None:
            params: dict[str, Any] = {}
        elif isinstance(raw_params, dict):
            params = raw_params
        else:
            return _jsonrpc_error(request_id, JSONRPC_INVALID_PARAMS, "params must be an object")
        try:
            if method == "message/send":
                result = await self._message_send(params)
                return _jsonrpc_success(request_id, result)
            if method == "tasks/get":
                result = self._tasks_get(params)
                return _jsonrpc_success(request_id, result)
            if method == "agent/getAuthenticatedExtendedCard":
                return _jsonrpc_success(request_id, build_agent_card(self.cfg))
        except ValueError as exc:
            return _jsonrpc_error(request_id, JSONRPC_INVALID_PARAMS, redact_text(str(exc)))
        except Exception:
            return _jsonrpc_error(request_id, JSONRPC_INTERNAL_ERROR, REMOTE_A2A_ERROR)
        return _jsonrpc_error(request_id, JSONRPC_METHOD_NOT_FOUND, "method not found")

    async def _message_send(self, params: dict[str, Any]) -> dict[str, Any]:
        request_message = params.get("message")
        if not isinstance(request_message, dict):
            raise ValueError("message object is required")
        operation = _extract_operation(params)
        sender = _extract_sender(params)
        context_id = params.get("contextId")
        context = str(context_id) if context_id is not None else None
        started = time.perf_counter()
        async with self.shim_factory(self.cfg) as shim:
            if operation["operation"] == "list_tools":
                resp = await handle_list_tools(None, sender, shim, self.cfg, self.audit)
                data = {
                    "ok": resp.error is None,
                    "operation": "list_tools",
                    "tools": resp.tools or [],
                    "error": resp.error,
                }
            else:
                tool = operation.get("tool")
                args = operation.get("args", {})
                if not isinstance(tool, str) or not tool:
                    raise ValueError("call_tool requires non-empty string tool")
                if not isinstance(args, dict):
                    raise ValueError("call_tool args must be an object")
                resp = await handle_call_tool(
                    None, sender, CallTool(tool=tool, args=args), shim, self.cfg, self.audit
                )
                data = {
                    "ok": resp.error is None,
                    "operation": "call_tool",
                    "tool": tool,
                    "result": resp.result,
                    "error": resp.error,
                }
        data["duration_ms"] = int((time.perf_counter() - started) * 1000)
        task = _completed_task(request_message, data, str(operation["operation"]), context)
        with self._tasks_lock:
            self.tasks[task["id"]] = task
        return task

    def _tasks_get(self, params: dict[str, Any]) -> dict[str, Any]:
        task_id = params.get("id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("tasks/get requires string id")
        with self._tasks_lock:
            task = self.tasks.get(task_id)
        if task is None:
            raise ValueError("task not found")
        return task


def _bearer_authorized(cfg: BridgeConfig, provided_header: str | None) -> bool:
    if not cfg.a2a.require_bearer_token:
        return True
    token = os.environ.get(cfg.a2a.bearer_token_env)
    if not token:
        return False
    expected = f"Bearer {token}"
    return hmac.compare_digest(
        (provided_header or "").encode("utf-8"),
        expected.encode("utf-8"),
    )


class AsyncLoopRunner:
    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, name="a2a-async-loop", daemon=True)
        self.thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run(self, coro: Any) -> Any:
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result()

    def close(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=5)
        self.loop.close()


class A2AHTTPHandler(BaseHTTPRequestHandler):
    server: "A2AHTTPServer"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _authorized(self) -> bool:
        return _bearer_authorized(
            self.server.bridge.cfg, self.headers.get("Authorization")
        )

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == self.server.bridge.cfg.a2a.agent_card_path:
            self._write_json(HTTPStatus.OK, build_agent_card(self.server.bridge.cfg))
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != self.server.bridge.cfg.a2a.rpc_path:
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        if not self._authorized():
            self._write_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
        except Exception:
            self._write_json(
                HTTPStatus.OK, _jsonrpc_error(None, -32700, "parse error or invalid JSON payload")
            )
            return
        response = self.server.run_jsonrpc(payload)
        self._write_json(HTTPStatus.OK, response)


class A2AHTTPServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], bridge: A2ABridge):
        super().__init__(address, A2AHTTPHandler)
        self.bridge = bridge
        self.async_runner = AsyncLoopRunner()

    def run_jsonrpc(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.async_runner.run(self.bridge.handle_jsonrpc(payload))

    def server_close(self) -> None:
        try:
            self.async_runner.close()
        finally:
            super().server_close()


def run_a2a_server(cfg: BridgeConfig) -> None:
    server = A2AHTTPServer((cfg.a2a.host, cfg.a2a.port), A2ABridge(cfg))
    try:
        server.serve_forever()
    finally:
        server.server_close()


async def run_local_a2a_roundtrip(cfg: BridgeConfig) -> tuple[dict[str, Any], dict[str, Any]]:
    bridge = A2ABridge(cfg)
    card = build_agent_card(cfg)
    request = {
        "jsonrpc": JSONRPC_VERSION,
        "id": "local-a2a-demo",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "parts": [{"kind": "data", "data": {"operation": "list_tools"}}],
            },
            "metadata": {"sender": "a2a:local-demo"},
        },
    }
    return card, await bridge.handle_jsonrpc(request)
