from __future__ import annotations

import asyncio
import contextlib
import importlib
import os
from contextlib import AsyncExitStack
from datetime import timedelta
from typing import Any, Self

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from ._redaction import redact_text
from .config import BridgeConfig
from .fake_mcp import _build_fake_server
from .result_normalizer import (
    NormalizedToolResult,
    error_result,
    from_call_tool_result,
    from_fastmcp_result,
)

HERMES_TOOLS_MODULE = "agent.transports.hermes_tools_mcp_server"


class HermesBackendError(RuntimeError):
    """The configured Hermes MCP backend could not be started."""


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


def _describe_startup_failure(exc: Exception, timeout_seconds: float) -> str:
    if isinstance(exc, TimeoutError):
        reason = f"timed out after {timeout_seconds:g}s waiting for the MCP server to initialize"
    elif isinstance(exc, FileNotFoundError):
        reason = f"command not found: {exc.filename or 'hermes_mcp.command'}"
    else:
        detail = redact_text(str(exc))[:300] or "no detail"
        reason = f"{exc.__class__.__name__}: {detail}"
    return (
        f"Hermes MCP server failed to start ({reason}). Its stderr is discarded; run the "
        "configured hermes_mcp.command and args by hand to see the error output."
    )


class HermesMCPClientShim:
    def __init__(self, cfg: BridgeConfig):
        self.cfg = cfg
        self.server: Any = None
        self.session: ClientSession | Any | None = None
        self._exit_stack: AsyncExitStack | None = None

    async def start(self) -> Self:
        """Start the backend, raising HermesBackendError if it is unusable.

        Failing here (rather than serving an empty tool list) makes `serve`
        exit non-zero, so a process supervisor can restart or alert.
        """
        mode = self.cfg.hermes_mcp.mode
        if mode == "fake":
            self.server = _build_fake_server()
        elif mode == "in_process_hermes_tools":
            try:
                module = importlib.import_module(HERMES_TOOLS_MODULE)
            except ImportError as exc:
                raise HermesBackendError(
                    f"{HERMES_TOOLS_MODULE} is not importable; install hermes-agent in this "
                    "environment or use hermes_mcp.mode: stdio"
                ) from exc
            self.server = module._build_server()
        elif mode == "stdio":
            if not self.cfg.hermes_mcp.command:
                raise ValueError("stdio command required")
            await self._start_stdio()
        else:
            raise NotImplementedError(f"{mode} transport is not enabled for local tests")
        return self

    async def _start_stdio(self) -> None:
        timeout_seconds = self.cfg.hermes_mcp.timeout_seconds
        self._exit_stack = stack = AsyncExitStack()
        # The child's stderr is outside the bridge's redaction boundary, so it is
        # discarded rather than logged. Opening os.devnull does not block.
        errlog = stack.enter_context(open(os.devnull, "w", encoding="utf-8"))  # noqa: ASYNC230, SIM115
        params = StdioServerParameters(
            command=self.cfg.hermes_mcp.command or "",
            args=list(self.cfg.hermes_mcp.args),
            env=filtered_env(),
        )
        try:
            read_stream, write_stream = await stack.enter_async_context(
                stdio_client(params, errlog=errlog)
            )
            session = await stack.enter_async_context(
                ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=timedelta(seconds=timeout_seconds),
                )
            )
            await asyncio.wait_for(session.initialize(), timeout=timeout_seconds)
        except Exception as exc:
            with contextlib.suppress(Exception):
                await self.aclose()
            raise HermesBackendError(_describe_startup_failure(exc, timeout_seconds)) from exc
        self.session = session

    async def aclose(self) -> None:
        stack, self._exit_stack = self._exit_stack, None
        self.session = None
        self.server = None
        if stack is not None:
            await stack.aclose()

    async def __aenter__(self) -> Self:
        return await self.start()

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def list_tools(self) -> list[dict[str, Any]]:
        if self.server is not None:
            tools = await self.server.list_tools()
            return [_tool_to_dict(t) for t in tools]
        if self.session is not None:
            result = await asyncio.wait_for(
                self.session.list_tools(), timeout=self.cfg.hermes_mcp.timeout_seconds
            )
            return [_tool_to_dict(t) for t in getattr(result, "tools", [])]
        raise RuntimeError("shim not started")

    async def call_tool(self, name: str, args: dict[str, Any]) -> NormalizedToolResult:
        max_bytes = self.cfg.policy.max_output_bytes
        try:
            if self.server is not None:
                return from_fastmcp_result(await self.server.call_tool(name, args), max_bytes)
            if self.session is not None:
                result = await asyncio.wait_for(
                    self.session.call_tool(name, args), timeout=self.cfg.hermes_mcp.timeout_seconds
                )
                return from_call_tool_result(result, max_bytes)
            raise RuntimeError("shim not started")
        except TimeoutError:
            return error_result("timeout", max_bytes)
        # Tool and transport failures become a bounded error result for the caller.
        except Exception as e:  # noqa: BLE001
            return error_result(str(e), max_bytes)
