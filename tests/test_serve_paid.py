"""A paid service end to end: `serve` in a subprocess, a loopback ledger, a remote buyer.

The ledger is a small HTTP server on 127.0.0.1 that answers the two Cosmos
REST calls the bridge makes and counts every request, which shows that a
bridge selling services does not contact the ledger until a paid call arrives.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from uagents.communication import send_sync_message
from uagents.crypto import Identity
from uagents.resolver import RulesBasedResolver
from uagents_adapter.mcp.protocol import CallTool, CallToolResponse, ListTools, ListToolsResponse

from hermes_fetch_ai.direct_protocol import replay_args
from hermes_fetch_ai.seller import parse_payment_terms
from hermes_fetch_ai.wallet import wallet_address

from .test_serve_http_roundtrip import _request_graceful_stop, _wait_for_port

SEED = "serve-paid-test-" + "identity-material-not-a-real-seed"
# Quotes are bound to the buyer, so the buyer keeps one identity across calls.
BUYER = Identity.from_seed("serve-paid-test-buyer-" + "identity-material", 0)
TX_HASH = "5B4A9D3C2E1F00112233445566778899AABBCCDDEEFF00112233445566778899"
NODE_INFO = "/cosmos/base/tendermint/v1beta1/node_info"
TXS = "/cosmos/tx/v1beta1/txs/"


class LoopbackLedger(ThreadingHTTPServer):
    """Answers node_info and transaction lookups; records every path asked for."""

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _LedgerHandler)
        self.requests: list[str] = []
        self.txs: dict[str, dict[str, Any]] = {}


class _LedgerHandler(BaseHTTPRequestHandler):
    server: LoopbackLedger

    def do_GET(self) -> None:
        self.server.requests.append(self.path)
        if self.path == NODE_INFO:
            self._send(200, {"default_node_info": {"network": "dorado-1"}})
        elif self.path.startswith(TXS) and self.path[len(TXS) :] in self.server.txs:
            self._send(200, self.server.txs[self.path[len(TXS) :]])
        else:
            self._send(404, {"code": 5, "message": "tx not found"})

    def _send(self, status: int, body: dict[str, Any]) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:
        pass


def msg_send(terms: dict[str, Any], payer: str) -> dict[str, Any]:
    """The REST answer for a transaction that pays ``terms`` exactly, made just now."""
    return {
        "tx": {
            "body": {
                "messages": [
                    {
                        "@type": "/cosmos.bank.v1beta1.MsgSend",
                        "from_address": payer,
                        "to_address": terms["recipient"],
                        "amount": [{"denom": terms["denom"], "amount": terms["amount_base"]}],
                    }
                ],
                "memo": terms["memo"],
            }
        },
        "tx_response": {
            "txhash": TX_HASH,
            "height": "4242",
            "code": 0,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    }


@pytest.fixture
def ledger() -> Iterator[LoopbackLedger]:
    server = LoopbackLedger()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def start_seller(tmp_path: Path, port: int, ledger: LoopbackLedger, services: str):
    endpoint = f"http://127.0.0.1:{port}/submit"
    cfg = tmp_path / "seller.yaml"
    cfg.write_text(
        "version: 1\n"
        "agent:\n"
        "  name: bridge_paid_smoke\n"
        f"  port: {port}\n"
        f"  endpoint: {endpoint}\n"
        "  mode: endpoint\n"
        "  publish_manifest: false\n"
        "  enable_agent_inspector: false\n"
        "hermes_mcp:\n"
        "  mode: fake\n"
        "payments:\n"
        "  enabled: true\n"
        f"  ledger_url: http://127.0.0.1:{ledger.server_address[1]}\n"
        f"  state_dir: {json.dumps(str(tmp_path / 'state'))}\n"
        "services:\n" + services + "logging:\n"
        f"  audit_path: {json.dumps(str(tmp_path / 'audit.jsonl'))}\n",
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["UAGENT_" + "SEED"] = SEED
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
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
    except BaseException:
        proc.kill()
        proc.wait(timeout=10)
        raise
    return proc, endpoint


def stop(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.kill()
        proc.wait(timeout=10)


@pytest.fixture
def seller(tmp_path: Path, unused_tcp_port: int, ledger: LoopbackLedger):
    research = (
        "  research:\n"
        "    title: Research a topic\n"
        "    description: Finds sources.\n"
        '    price: "0.05"\n'
        "    runner: {type: echo}\n"
    )
    proc, endpoint = start_seller(tmp_path, unused_tcp_port, ledger, research)
    try:
        yield proc, endpoint
    finally:
        stop(proc)


@pytest.fixture
def slow_seller(tmp_path: Path, unused_tcp_port: int, ledger: LoopbackLedger):
    script = tmp_path / "slow.py"
    script.write_text(
        "import json, sys, time\njson.load(sys.stdin)\ntime.sleep(3)\nprint('done')\n"
    )
    slow = (
        "  slow:\n"
        "    title: Slow\n"
        "    description: Takes three seconds.\n"
        "    runner:\n"
        "      type: command\n"
        f"      argv: {json.dumps([sys.executable, str(script)])}\n"
    )
    proc, endpoint = start_seller(tmp_path, unused_tcp_port, ledger, slow)
    try:
        yield proc, endpoint
    finally:
        stop(proc)


async def test_paid_call_through_serve(seller, ledger, tmp_path):
    proc, endpoint = seller
    address = Identity.from_seed(SEED, 0).address
    resolver = RulesBasedResolver({address: endpoint})

    async def call(args: dict[str, Any], sender: Identity = BUYER) -> CallToolResponse:
        reply = await send_sync_message(
            address,
            CallTool(tool="service.research", args=args),
            response_type=CallToolResponse,
            sender=sender,
            resolver=resolver,
            timeout=20,
        )
        assert isinstance(reply, CallToolResponse)
        return reply

    listed = await send_sync_message(
        address, ListTools(), response_type=ListToolsResponse, resolver=resolver, timeout=20
    )
    assert isinstance(listed, ListToolsResponse)
    assert [t["name"] for t in listed.tools or []] == ["service.research"]

    unpaid = await call(replay_args({"request": "tides"}))
    terms = parse_payment_terms(unpaid.error)
    assert terms is not None and terms["amount"] == "0.05"
    assert terms["recipient"] == wallet_address(SEED)  # no payout_address: the agent's wallet
    # Starting, listing, and quoting never touched the ledger.
    assert ledger.requests == []

    ledger.txs[TX_HASH] = msg_send(terms, payer="fetch1buyer")
    proof = {"reference": terms["reference"], "tx_hash": TX_HASH.lower()}
    paid = await call(replay_args({"request": "tides"}, payment=proof))
    assert (paid.result, paid.error) == ("tides", None)
    assert ledger.requests == [NODE_INFO, TXS + TX_HASH]

    # The buyer asking again gets the same answer; another agent presenting the
    # same (public) payment gets nothing. Neither asks the ledger again.
    again = await call(replay_args({"request": "tides"}, payment=proof))
    assert (again.result, again.error) == ("tides", None)
    thief = Identity.from_seed("serve-paid-test-thief-" + "identity-material", 0)
    stolen = await call(replay_args({"request": "tides"}, payment=proof), sender=thief)
    assert (stolen.result, stolen.error) == (None, "quote does not match this call")
    assert len(ledger.requests) == 2

    rc = _request_graceful_stop(proc)
    output = proc.stdout.read() if proc.stdout else ""
    assert rc == 0, f"serve did not shut down cleanly (rc={rc}):\n{output[-2000:]}"
    assert SEED not in output and TX_HASH not in output.upper()
    audit = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert TX_HASH not in audit.upper() and terms["reference"] not in audit
    assert '"payment": "verified"' in audit


def run_example(
    seller, *extra: str, payer_seed: str | None = None
) -> subprocess.CompletedProcess[str]:
    _, endpoint = seller
    env = {k: v for k, v in os.environ.items() if k != "HERMES_FETCH_PAYER_SEED"}
    if payer_seed:
        env["HERMES_FETCH_PAYER_SEED"] = payer_seed
    example = Path(__file__).parents[1] / "examples" / "call_bridge.py"
    address = Identity.from_seed(SEED, 0).address
    return subprocess.run(
        [sys.executable, str(example), address, endpoint, "--tool", "service.research", *extra],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=env,
    )


def test_example_client_shows_the_price(seller, ledger):
    res = run_example(seller, "--request", "tides")
    assert res.returncode == 0, res.stderr[-2000:]
    assert "tools: ['service.research']" in res.stdout
    assert f"price: 0.05 testnet FET to {wallet_address(SEED)}" in res.stdout
    assert "add --pay" in res.stdout
    assert ledger.requests == []


def test_example_client_pays_only_within_its_limits(seller, ledger):
    no_seed = run_example(seller, "--request", "tides", "--pay")
    assert no_seed.returncode == 1 and "--pay needs HERMES_FETCH_PAYER_SEED" in no_seed.stderr
    too_dear = run_example(
        seller, "--request", "tides", "--pay", "--max-fet", "0.01", payer_seed="payer-" + "x" * 40
    )
    assert too_dear.returncode == 1, too_dear.stderr[-2000:]
    assert "refusing to pay 0.05 FET: more than --max-fet 0.01" in too_dear.stderr
    assert ledger.requests == []


async def test_a_long_run_does_not_hold_up_other_requests(slow_seller, ledger):
    _, endpoint = slow_seller
    address = Identity.from_seed(SEED, 0).address
    resolver = RulesBasedResolver({address: endpoint})
    run = asyncio.create_task(
        send_sync_message(
            address,
            CallTool(tool="service.slow", args=replay_args({"request": "x"})),
            response_type=CallToolResponse,
            sender=BUYER,
            resolver=resolver,
            timeout=30,
        )
    )
    await asyncio.sleep(0.5)  # the three-second run has started
    started = time.monotonic()
    listed = await send_sync_message(
        address, ListTools(), response_type=ListToolsResponse, resolver=resolver, timeout=20
    )
    assert time.monotonic() - started < 2.0, "the listing waited for the run"
    assert isinstance(listed, ListToolsResponse)
    reply = await run
    assert isinstance(reply, CallToolResponse) and reply.result == "done"
    assert ledger.requests == []  # a free service never touches the ledger
