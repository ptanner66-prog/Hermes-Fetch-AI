from __future__ import annotations

import asyncio
import contextlib
import importlib
import os
from contextlib import AsyncExitStack
from datetime import timedelta
from typing import Any, Protocol, Self

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from ._redaction import redact_text
from .config import HERMES_PYTHON_VAR, HERMES_PYTHONPATH_VAR, BridgeConfig
from .fake_mcp import build_fake_server
from .logging import get_logger
from .result_normalizer import (
    NormalizedToolResult,
    error_result,
    from_call_tool_result,
    from_fastmcp_result,
)

HERMES_TOOLS_MODULE = "agent.transports.hermes_tools_mcp_server"
HERMES_TOOLS_SERVER_ARGS = ("-m", HERMES_TOOLS_MODULE)

logger = get_logger("hermes_fetch_ai")


class HermesBackendError(RuntimeError):
    """The configured Hermes MCP backend could not be started."""


class ToolBackend(Protocol):
    """What the bridge protocol needs from a tool backend."""

    async def list_tools(self) -> list[dict[str, Any]]:
        """Tool descriptors with ``name``, ``description`` and ``inputSchema`` keys."""
        ...

    async def call_tool(self, name: str, args: dict[str, Any]) -> NormalizedToolResult: ...


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


def stdio_parameters(cfg: BridgeConfig) -> StdioServerParameters:
    """How to launch the Hermes tools MCP server.

    An explicit ``hermes_mcp.command`` wins. Otherwise use the interpreter and
    import path of the Hermes that launched the bridge (passed by the
    fetchai-bridge plugin), which is how Hermes starts this server itself.
    """
    env = filtered_env()
    # Hermes sets these when it launches its tools server, to keep the MCP wire clean.
    env.setdefault("HERMES_QUIET", "1")
    env.setdefault("HERMES_REDACT_SECRETS", "true")
    command = cfg.hermes_mcp.command or ""
    args = list(cfg.hermes_mcp.args)
    if not command:
        command = os.environ.get(HERMES_PYTHON_VAR, "")
        args = args or list(HERMES_TOOLS_SERVER_ARGS)
        pythonpath = os.environ.get(HERMES_PYTHONPATH_VAR)
        if pythonpath:
            env["PYTHONPATH"] = pythonpath
    if not command:
        raise ValueError("stdio command required")
    return StdioServerParameters(command=command, args=args, env=env)


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


def _describe_startup_failure(
    exc: Exception, timeout_seconds: float, params: StdioServerParameters
) -> str:
    if isinstance(exc, TimeoutError):
        reason = f"timed out after {timeout_seconds:g}s waiting for the MCP server to initialize"
    elif isinstance(exc, FileNotFoundError):
        reason = f"command not found: {exc.filename or 'hermes_mcp.command'}"
    else:
        detail = redact_text(str(exc))[:300] or "no detail"
        reason = f"{exc.__class__.__name__}: {detail}"
    # Name the command, which may come from the Hermes plugin rather than the
    # config; custom args are left out of the message.
    if tuple(params.args) == HERMES_TOOLS_SERVER_ARGS:
        how = f"`{' '.join([params.command, *HERMES_TOOLS_SERVER_ARGS])}`"
    else:
        how = f"`{params.command}` with the configured args"
    if params.env and "PYTHONPATH" in params.env:
        how += " and Hermes' PYTHONPATH"
    return (
        f"Hermes MCP server failed to start ({reason}). Its stderr is discarded; "
        f"run {redact_text(how)} by hand to see the error output."
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
            self.server = build_fake_server()
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
            await self._start_stdio()
        else:
            raise HermesBackendError(f"unsupported hermes_mcp.mode: {mode}")
        return self

    async def _start_stdio(self) -> None:
        timeout_seconds = self.cfg.hermes_mcp.timeout_seconds
        params = stdio_parameters(self.cfg)
        self._exit_stack = stack = AsyncExitStack()
        # The child's stderr is outside the bridge's redaction boundary, so it is
        # discarded rather than logged. Opening os.devnull does not block.
        errlog = stack.enter_context(open(os.devnull, "w", encoding="utf-8"))  # noqa: ASYNC230, SIM115
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
            raise HermesBackendError(
                _describe_startup_failure(exc, timeout_seconds, params)
            ) from exc
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
        except Exception as exc:  # noqa: BLE001
            # Transport and protocol errors can carry internal details such as file
            # paths, so the caller gets a fixed message and the details are logged.
            logger.warning(
                "Hermes tool call %s failed (%s: %s)",
                name,
                exc.__class__.__name__,
                redact_text(str(exc))[:300],
            )
            return error_result("tool call failed", max_bytes)
