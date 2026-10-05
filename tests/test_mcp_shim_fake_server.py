import asyncio
import os
import sys
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from hermes_fetch_ai.config import BridgeConfig
from hermes_fetch_ai.mcp_shim import HermesBackendError, HermesMCPClientShim, filtered_env


def cfg(**kw):
    data = {"agent": {"dev_random_seed": True}, "policy": {"public_tools": ["echo", "add"]}}
    data.update(kw)
    return BridgeConfig(**data)


@pytest.mark.asyncio
async def test_fake_list_tools_returns_echo_add():
    async with HermesMCPClientShim(cfg(hermes_mcp={"mode": "fake"})) as shim:
        names = {t["name"] for t in await shim.list_tools()}
    assert {"echo", "add"} <= names


@pytest.mark.asyncio
async def test_fake_call_tool_returns_normalized_result():
    async with HermesMCPClientShim(cfg(hermes_mcp={"mode": "fake"})) as shim:
        out = await shim.call_tool("echo", {"text": "hi"})
    assert out.text == "hi"


@pytest.mark.asyncio
async def test_in_process_result_path_uses_fastmcp_result():
    async with HermesMCPClientShim(cfg(hermes_mcp={"mode": "fake"})) as shim:
        out = await shim.call_tool("add", {"a": 2, "b": 3})
    assert out.text == "5"


@pytest.mark.asyncio
async def test_stdio_fake_subprocess_launches_with_filtered_env():
    c = cfg(
        hermes_mcp={
            "mode": "stdio",
            "command": sys.executable,
            "args": ["tests/fakes/fake_mcp_subprocess.py"],
        }
    )
    async with HermesMCPClientShim(c) as shim:
        assert (await shim.call_tool("echo", {"text": "ok"})).text == "ok"


@pytest.mark.asyncio
async def test_stdio_uses_mcp_client_session_interface(monkeypatch):
    events = []

    @asynccontextmanager
    async def fake_stdio_client(params, errlog):
        events.append(
            ("stdio", params.command, list(params.args), bool(params.env), errlog is not None)
        )
        yield "read-stream", "write-stream"

    class FakeSession:
        def __init__(self, read_stream, write_stream, read_timeout_seconds=None):
            events.append(
                ("session_init", read_stream, write_stream, read_timeout_seconds is not None)
            )

        async def __aenter__(self):
            events.append(("session_enter",))
            return self

        async def __aexit__(self, *exc):
            events.append(("session_exit",))

        async def initialize(self):
            events.append(("initialize",))

        async def list_tools(self):
            events.append(("list_tools",))
            return SimpleNamespace(tools=[{"name": "echo", "inputSchema": None}])

        async def call_tool(self, name, args):
            events.append(("call_tool", name, args))
            return {"content": [{"type": "text", "text": args["text"]}], "isError": False}

    monkeypatch.setattr("hermes_fetch_ai.mcp_shim.stdio_client", fake_stdio_client)
    monkeypatch.setattr("hermes_fetch_ai.mcp_shim.ClientSession", FakeSession)
    c = cfg(hermes_mcp={"mode": "stdio", "command": "cmd", "args": ["--serve"]})
    async with HermesMCPClientShim(c) as shim:
        assert (await shim.list_tools())[0]["name"] == "echo"
        assert (await shim.call_tool("echo", {"text": "ok"})).text == "ok"
    assert ("stdio", "cmd", ["--serve"], True, True) in events
    assert ("initialize",) in events
    assert ("list_tools",) in events
    assert ("call_tool", "echo", {"text": "ok"}) in events
    assert ("session_exit",) in events


def test_windows_env_allowlist_includes_expected_when_present(monkeypatch):
    for k in ["SystemRoot", "WINDIR", "PATHEXT", "TEMP", "TMP"]:
        monkeypatch.setenv(k, "x")
    env = filtered_env()
    if os.name == "nt":
        assert all(k in env for k in ["SystemRoot", "WINDIR", "PATHEXT", "TEMP", "TMP"])


@pytest.mark.asyncio
async def test_startup_timeout_raises_backend_error():
    c = cfg(
        hermes_mcp={
            "mode": "stdio",
            "command": sys.executable,
            "args": ["-c", "import time; time.sleep(5)"],
            "timeout_seconds": 0.1,
        }
    )
    with pytest.raises(HermesBackendError, match="(?i)timed out"):
        async with HermesMCPClientShim(c):
            pass


@pytest.mark.asyncio
async def test_broken_subprocess_fails_fast_without_stderr_secret_leak(capfd):
    marker = "s" + "k-secret"
    c = cfg(
        hermes_mcp={
            "mode": "stdio",
            "command": sys.executable,
            "args": [
                "-c",
                f"import sys; print({marker!r}, file=sys.stderr); sys.exit(2)",
            ],
            "timeout_seconds": 5,
        }
    )
    with pytest.raises(HermesBackendError) as exc:
        async with HermesMCPClientShim(c):
            pass
    captured = capfd.readouterr()
    assert marker not in str(exc.value)
    assert marker not in captured.out + captured.err


@pytest.mark.asyncio
async def test_missing_command_raises_backend_error():
    c = cfg(hermes_mcp={"mode": "stdio", "command": "/nonexistent/hermes-python"})
    with pytest.raises(HermesBackendError, match="command not found"):
        async with HermesMCPClientShim(c):
            pass


@pytest.mark.asyncio
async def test_in_process_mode_without_hermes_raises_backend_error():
    with pytest.raises(HermesBackendError, match="not importable"):
        async with HermesMCPClientShim(cfg(hermes_mcp={"mode": "in_process_hermes_tools"})):
            pass


@pytest.mark.asyncio
async def test_call_timeout_returns_structured_error(monkeypatch):
    @asynccontextmanager
    async def fake_stdio_client(params, errlog):
        yield "read-stream", "write-stream"

    class HangingSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def initialize(self):
            return None

        async def call_tool(self, name, args):
            await asyncio.sleep(30)

    monkeypatch.setattr("hermes_fetch_ai.mcp_shim.stdio_client", fake_stdio_client)
    monkeypatch.setattr("hermes_fetch_ai.mcp_shim.ClientSession", HangingSession)
    c = cfg(hermes_mcp={"mode": "stdio", "command": "cmd", "timeout_seconds": 0.1})
    async with HermesMCPClientShim(c) as shim:
        out = await shim.call_tool("echo", {"text": "x"})
    assert out.is_error and out.text == "timeout"


@pytest.mark.asyncio
async def test_tool_error_text_is_size_capped():
    c = cfg(hermes_mcp={"mode": "fake"}, policy={"public_tools": [], "max_output_bytes": 16})
    async with HermesMCPClientShim(c) as shim:
        out = await shim.call_tool("x" * 500, {})
    assert out.is_error and out.truncated
    assert len(out.text.encode("utf-8")) <= 16
    assert out.output_bytes > 16


@pytest.mark.asyncio
async def test_unstarted_shim_does_not_pretend_to_have_no_tools():
    with pytest.raises(RuntimeError, match="not started"):
        await HermesMCPClientShim(cfg(hermes_mcp={"mode": "fake"})).list_tools()
