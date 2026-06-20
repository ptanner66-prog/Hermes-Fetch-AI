from __future__ import annotations

import asyncio
import os
from contextlib import AsyncExitStack
from datetime import timedelta
from typing import Any, TextIO

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from .config import BridgeConfig
from .fake_mcp import _build_fake_server
from .result_normalizer import NormalizedToolResult, from_call_tool_result, from_fastmcp_result


def filtered_env() -> dict[str, str]:
    allowed = {
        "PATH",
        "HOME",
        "TMPDIR",
        "HERMES_HOME",
        "HERMES_QUIET",
        "HERMES_REDACT_SECRETS",
        "LANG",
        "LC_ALL",
    }
    if os.name == "nt":
        allowed |= {"PATHEXT", "SystemRoot", "WINDIR", "TEMP", "TMP", "USERPROFILE"}
    allowed_lower = {k.lower() for k in allowed}
    env = {k: v for k, v in os.environ.items() if k in allowed or k.lower() in allowed_lower}
    if os.name == "nt":
        for canonical in ("SystemRoot", "WINDIR", "PATHEXT", "TEMP", "TMP"):
            for k, v in os.environ.items():
                if k.lower() == canonical.lower():
                    env[canonical] = v
                    break
    return env


def _tool_to_dict(tool: Any) -> dict[str, Any]:
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
    d["inputSchema"] = d.get("inputSchema") or {"type": "object", "properties": {}}
    return d


class HermesMCPClientShim:
    def __init__(self, cfg: BridgeConfig):
        self.cfg = cfg
        self.server: Any = None
        self.session: ClientSession | Any | None = None
        self._exit_stack: AsyncExitStack | None = None
        self._errlog: TextIO | None = None
        self._startup_error: BaseException | None = None

    async def start(self) -> "HermesMCPClientShim":
        mode = self.cfg.hermes_mcp.mode
        if mode == "fake":
            self.server = _build_fake_server()
        elif mode == "in_process_hermes_tools":
            mod = __import__("agent.transports.hermes_tools_mcp_server", fromlist=["_build_server"])
            self.server = mod._build_server()
        elif mode == "stdio":
            if not self.cfg.hermes_mcp.command:
                raise ValueError("stdio command required")
            await self._start_stdio()
        else:
            raise NotImplementedError(f"{mode} transport is not enabled for local tests")
        return self

    async def _start_stdio(self) -> None:
        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()
        self._errlog = open(os.devnull, "w", encoding="utf-8")
        self._exit_stack.callback(self._errlog.close)
        params = StdioServerParameters(
            command=self.cfg.hermes_mcp.command or "",
            args=list(self.cfg.hermes_mcp.args),
            env=filtered_env(),
        )
        try:
            read_stream, write_stream = await self._exit_stack.enter_async_context(
                stdio_client(params, errlog=self._errlog)
            )
            timeout = timedelta(seconds=self.cfg.hermes_mcp.timeout_seconds)
            self.session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream, read_timeout_seconds=timeout)
            )
            await asyncio.wait_for(
                self.session.initialize(), timeout=self.cfg.hermes_mcp.timeout_seconds
            )
        except BaseException as exc:
            self._startup_error = exc

    async def aclose(self) -> None:
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
            self._exit_stack = None
        self.session = None
        self.server = None

    async def __aenter__(self) -> "HermesMCPClientShim":
        return await self.start()

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def list_tools(self) -> list[dict[str, Any]]:
        if self.server is not None:
            tools = await self.server.list_tools()
            return [_tool_to_dict(t) for t in tools]
        if self._startup_error is not None:
            return []
        if self.session is not None:
            result = await asyncio.wait_for(
                self.session.list_tools(), timeout=self.cfg.hermes_mcp.timeout_seconds
            )
            return [_tool_to_dict(t) for t in getattr(result, "tools", [])]
        return []

    async def call_tool(self, name: str, args: dict[str, Any]) -> NormalizedToolResult:
        try:
            if self.server is not None:
                return from_fastmcp_result(
                    await self.server.call_tool(name, args), self.cfg.policy.max_output_bytes
                )
            if self._startup_error is not None:
                if (
                    isinstance(self._startup_error, (TimeoutError, asyncio.TimeoutError))
                    or "timed out" in str(self._startup_error).lower()
                ):
                    return NormalizedToolResult("timeout", None, True, False, 7)
                return NormalizedToolResult(
                    "MCP stdio startup failed", None, True, False, len("MCP stdio startup failed")
                )
            if self.session is not None:
                result = await asyncio.wait_for(
                    self.session.call_tool(name, args), timeout=self.cfg.hermes_mcp.timeout_seconds
                )
                return from_call_tool_result(result, self.cfg.policy.max_output_bytes)
            raise RuntimeError("shim not started")
        except (TimeoutError, asyncio.TimeoutError):
            return NormalizedToolResult("timeout", None, True, False, 7)
        except Exception as e:
            text = str(e)
            return NormalizedToolResult(text, None, True, False, len(text.encode()))
