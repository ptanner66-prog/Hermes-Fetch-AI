"""A loopback stand-in for an OpenAI-compatible model API, for tests that run real Hermes.

It answers ``POST /v1/chat/completions`` from a script of replies, streamed or
not, and records every request, so a test can check exactly which tools and
instructions a guest Hermes offered the model. Given ``accepted_fields``, it is
as strict as ASI:One's API: a request with any other top-level field gets a 400
``unknown_parameter`` error naming it, in ASI:One's documented error shape.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Self

MODEL = "fake-model"


def text_reply(text: str) -> dict[str, Any]:
    return {"content": text}


def tool_reply(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {"tool_calls": [{"name": name, "arguments": arguments}]}


class FakeModelServer:
    """Serves scripted replies on 127.0.0.1; the last reply repeats once the script runs out."""

    def __init__(
        self, replies: list[dict[str, Any]], accepted_fields: frozenset[str] | None = None
    ) -> None:
        self.replies = list(replies)
        self.accepted_fields = accepted_fields
        self.requests: list[dict[str, Any]] = []
        self.rejected: list[list[str]] = []  # the unknown fields of each refused request
        self.authorizations: list[str] = []
        self.paths: list[str] = []
        self._lock = threading.Lock()
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                pass

            def do_GET(self) -> None:
                server.paths.append(f"GET {self.path}")
                if self.path.rstrip("/").endswith("/models"):
                    self._json(200, {"object": "list", "data": [_model_card()]})
                elif "/models/" in self.path:
                    self._json(200, _model_card())
                else:
                    self._json(404, {"error": {"message": "not found"}})

            def do_POST(self) -> None:
                server.paths.append(f"POST {self.path}")
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                server.authorizations.append(self.headers.get("Authorization") or "")
                if not self.path.rstrip("/").endswith("/chat/completions"):
                    self._json(404, {"error": {"message": f"unsupported path {self.path}"}})
                    return
                unknown = (
                    sorted(set(body) - server.accepted_fields) if server.accepted_fields else []
                )
                if unknown:
                    server.rejected.append(unknown)
                    error = {
                        "message": f"Unknown parameter: '{unknown[0]}'.",
                        "type": "invalid_request_error",
                        "code": "unknown_parameter",
                        "param": unknown[0],
                        "status": 400,
                    }
                    self._json(400, {"error": error})
                    return
                reply = server._next(body)
                if body.get("stream"):
                    self._stream(reply, body)
                else:
                    self._json(200, _completion(reply))

            def _json(self, status: int, payload: dict[str, Any]) -> None:
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _stream(self, reply: dict[str, Any], body: dict[str, Any]) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                for chunk in _chunks(reply, include_usage=_wants_usage(body)):
                    self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                    self.wfile.flush()
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._httpd.server_port}/v1"

    def _next(self, body: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self.requests.append(body)
            return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]

    def offered_tools(self) -> set[str]:
        """Every tool name any request offered the model."""
        return {
            tool["function"]["name"]
            for request in self.requests
            for tool in request.get("tools") or []
        }

    def __enter__(self) -> Self:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


def _model_card() -> dict[str, Any]:
    return {"id": MODEL, "object": "model", "created": 0, "owned_by": "tests"}


def _wants_usage(body: dict[str, Any]) -> bool:
    return bool((body.get("stream_options") or {}).get("include_usage"))


def _usage() -> dict[str, int]:
    return {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


def _tool_calls(reply: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": f"call_{index}",
            "type": "function",
            "function": {"name": call["name"], "arguments": json.dumps(call["arguments"])},
        }
        for index, call in enumerate(reply.get("tool_calls") or [])
    ]


def _completion(reply: dict[str, Any]) -> dict[str, Any]:
    calls = _tool_calls(reply)
    message: dict[str, Any] = {"role": "assistant", "content": reply.get("content")}
    if calls:
        message["tool_calls"] = calls
    return {
        "id": "chatcmpl-fake",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": MODEL,
        "choices": [
            {"index": 0, "message": message, "finish_reason": "tool_calls" if calls else "stop"}
        ],
        "usage": _usage(),
    }


def _chunks(reply: dict[str, Any], *, include_usage: bool) -> list[dict[str, Any]]:
    def chunk(delta: dict[str, Any], finish: str | None = None) -> dict[str, Any]:
        return {
            "id": "chatcmpl-fake",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": MODEL,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        }

    calls = _tool_calls(reply)
    chunks = [chunk({"role": "assistant", "content": ""})]
    if reply.get("content"):
        chunks.append(chunk({"content": reply["content"]}))
    for index, call in enumerate(calls):
        chunks.append(chunk({"tool_calls": [{"index": index, **call}]}))
    chunks.append(chunk({}, "tool_calls" if calls else "stop"))
    if include_usage:
        chunks.append({**chunk({}), "choices": [], "usage": _usage()})
    return chunks
