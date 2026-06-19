"""Production smoke: the serve entry point over real HTTP, two processes.

A bridge subprocess runs `hermes_fetch_ai.cli serve` (endpoint mode, fake
tools). The test acts as a remote client: it resolves the bridge address to
its localhost endpoint with a RulesBasedResolver (no Almanac, fully offline)
and exchanges signed envelopes over HTTP, then asserts graceful shutdown. This
is the path production deployments actually run.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from uagents.communication import send_sync_message
from uagents.crypto import Identity
from uagents.resolver import RulesBasedResolver
from uagents_adapter.mcp.protocol import CallTool, CallToolResponse, ListTools, ListToolsResponse

from hermes_fetch_ai.direct_protocol import replay_args

LOCAL_IDENTITY_TEXT = "serve-http-roundtrip-test-" + "identity-material"


def _wait_for_port(port: int, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.3)
    raise TimeoutError(f"bridge never opened port {port}")


def _request_graceful_stop(proc: subprocess.Popen[str], timeout: float = 30.0) -> int:
    """Ask the bridge subprocess to stop, retrying Windows console delivery.

    Windows CTRL_BREAK delivery can be flaky under captured test runners even
    when the child is in its own process group. Retrying keeps the assertion on
    the production behavior we care about: the process exits by its installed
    handler with rc=0, not by fixture kill/TerminateProcess.
    """

    deadline = time.monotonic() + timeout
    signal_to_send = signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGTERM
    while proc.poll() is None and time.monotonic() < deadline:
        proc.send_signal(signal_to_send)
        remaining = max(0.1, min(5.0, deadline - time.monotonic()))
        try:
            return proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            continue
    if proc.poll() is None:
        raise subprocess.TimeoutExpired(proc.args, timeout)
    return proc.returncode


@pytest.fixture
def bridge_proc(tmp_path: Path, unused_tcp_port: int):
    port = unused_tcp_port
    endpoint = f"http://127.0.0.1:{port}/submit"
    cfg = tmp_path / "serve.yaml"
    cfg.write_text(
        "version: 1\n"
        "agent:\n"
        "  name: bridge_http_smoke\n"
        f"  port: {port}\n"
        f"  endpoint: {endpoint}\n"
        "  mode: endpoint\n"
        "  publish_manifest: false\n"
        "  enable_agent_inspector: false\n"
        "  dev_random_seed: false\n"
        "hermes_mcp:\n"
        "  mode: fake\n"
        "policy:\n"
        "  public_tools: [echo]\n"
        "logging:\n"
        "  redaction: true\n"
        f"  audit_path: {tmp_path / 'audit.jsonl'}\n",
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["UAGENT_" + "SEED"] = LOCAL_IDENTITY_TEXT
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    proc = subprocess.Popen(
        [sys.executable, "-m", "hermes_fetch_ai.cli", "serve", "--config", str(cfg)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=creationflags,
    )
    try:
        _wait_for_port(port)
        yield proc, endpoint
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)


@pytest.mark.asyncio
async def test_serve_http_roundtrip_and_graceful_shutdown(bridge_proc):
    proc, endpoint = bridge_proc
    address = Identity.from_seed(LOCAL_IDENTITY_TEXT, 0).address
    resolver = RulesBasedResolver({address: endpoint})

    listed = await send_sync_message(
        address, ListTools(), response_type=ListToolsResponse, resolver=resolver, timeout=20
    )
    assert isinstance(listed, ListToolsResponse)
    assert [t["name"] for t in (listed.tools or [])] == ["echo"]

    call = await send_sync_message(
        address,
        CallTool(tool="echo", args=replay_args({"text": "prod"}, request_id="serve-call-0001")),
        response_type=CallToolResponse,
        resolver=resolver,
        timeout=20,
    )
    assert isinstance(call, CallToolResponse)
    assert call.result == "prod" and call.error is None

    denied = await send_sync_message(
        address,
        CallTool(tool="add", args=replay_args({"a": 1, "b": 2}, request_id="serve-deny-0001")),
        response_type=CallToolResponse,
        resolver=resolver,
        timeout=20,
    )
    assert isinstance(denied, CallToolResponse)
    assert denied.result is None and denied.error

    rc = _request_graceful_stop(proc)
    output = proc.stdout.read() if proc.stdout else ""
    assert rc == 0, f"serve did not shut down cleanly (rc={rc}):\n{output[-2000:]}"
    assert LOCAL_IDENTITY_TEXT not in output
