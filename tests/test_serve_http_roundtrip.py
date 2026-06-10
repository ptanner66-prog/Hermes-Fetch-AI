"""Production smoke: the serve entry point over real HTTP, two processes.

A bridge subprocess runs `hermes_fetch_ai.cli serve` (endpoint mode, fake
tools). The test acts as a remote client: it resolves the bridge address to
its localhost endpoint with a RulesBasedResolver (no Almanac, fully offline)
and exchanges signed envelopes over HTTP, then asserts graceful SIGTERM
shutdown. This is the path production deployments actually run.
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

SEED = "serve-http-roundtrip-test-seed-not-secret"
PORT = 8765
ENDPOINT = f"http://127.0.0.1:{PORT}/submit"


def _wait_for_port(port: int, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.3)
    raise TimeoutError(f"bridge never opened port {port}")


@pytest.fixture
def bridge_proc(tmp_path: Path):
    cfg = tmp_path / "serve.yaml"
    cfg.write_text(
        "version: 1\n"
        "agent:\n"
        "  name: bridge_http_smoke\n"
        f"  port: {PORT}\n"
        f"  endpoint: {ENDPOINT}\n"
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
    env = dict(os.environ, UAGENT_SEED=SEED)
    proc = subprocess.Popen(
        [sys.executable, "-m", "hermes_fetch_ai.cli", "serve", "--config", str(cfg)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_for_port(PORT)
        yield proc
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)


@pytest.mark.asyncio
async def test_serve_http_roundtrip_and_graceful_sigterm(bridge_proc):
    address = Identity.from_seed(SEED, 0).address
    resolver = RulesBasedResolver({address: ENDPOINT})

    listed = await send_sync_message(
        address, ListTools(), response_type=ListToolsResponse, resolver=resolver, timeout=20
    )
    assert isinstance(listed, ListToolsResponse)
    assert [t["name"] for t in (listed.tools or [])] == ["echo"]

    call = await send_sync_message(
        address,
        CallTool(tool="echo", args={"text": "prod"}),
        response_type=CallToolResponse,
        resolver=resolver,
        timeout=20,
    )
    assert isinstance(call, CallToolResponse)
    assert call.result == "prod" and call.error is None

    denied = await send_sync_message(
        address,
        CallTool(tool="add", args={"a": 1, "b": 2}),
        response_type=CallToolResponse,
        resolver=resolver,
        timeout=20,
    )
    assert isinstance(denied, CallToolResponse)
    assert denied.result is None and denied.error

    bridge_proc.send_signal(signal.SIGTERM)
    rc = bridge_proc.wait(timeout=20)
    output = bridge_proc.stdout.read() if bridge_proc.stdout else ""
    assert rc == 0, f"serve did not shut down cleanly (rc={rc}):\n{output[-2000:]}"
    assert SEED not in output
