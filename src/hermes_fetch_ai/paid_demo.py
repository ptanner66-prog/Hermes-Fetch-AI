"""An offline walk through selling a service: quote, pay, run, and refuse reuse.

Two uAgents talk through uAgents' in-process dispatcher, and payments go to
an in-memory ledger, so the demo needs no network, seed, or funds.
"""

from __future__ import annotations

from pathlib import Path

from uagents.dispatch import dispatcher
from uagents_adapter.mcp.protocol import CallTool, CallToolResponse

from .config import BridgeConfig
from .direct_protocol import replay_args
from .fake_ledger import FakeLedger
from .mcp_shim import HermesMCPClientShim
from .seller import parse_payment_terms, short_tx
from .uagent_app import build_agent, build_service_desk, local_dispatch_request
from .wallet import wallet_address

# Public, well-known demo identities: never put real funds behind these.
DEMO_SELLER_WALLET_SEED = "hermes-fetch-ai paid demo seller wallet (public, test only)"
DEMO_BUYER_WALLET_SEED = "hermes-fetch-ai paid demo buyer wallet (public, test only)"
DEMO_SERVICE = "echo"


def paid_demo_config(state_dir: Path) -> BridgeConfig:
    return BridgeConfig.model_validate(
        {
            "agent": {"name": "hermes_fetch_paid_demo", "dev_random_seed": True},
            "hermes_mcp": {"mode": "fake"},
            "payments": {
                "enabled": True,
                "payout_address": wallet_address(DEMO_SELLER_WALLET_SEED),
                "state_dir": str(state_dir),
            },
            "services": {
                DEMO_SERVICE: {
                    "title": "Echo",
                    "description": "Answers with your request (a demo service).",
                    "price": "0.05",
                    "runner": {"type": "echo"},
                    "disclaimer": "Demo service on Fetch's testnet; no real money involved.",
                }
            },
            "logging": {"audit_path": str(state_dir / "audit.jsonl")},
        }
    )


async def run_paid_demo(state_dir: Path) -> list[str]:
    """Run the demo and return what happened, one line per step."""
    cfg = paid_demo_config(state_dir)
    ledger = FakeLedger()
    seed = cfg.effective_seed()
    tool = f"service.{DEMO_SERVICE}"
    lines: list[str] = []
    async with HermesMCPClientShim(cfg) as shim:
        desk = build_service_desk(cfg, seed, ledger_factory=lambda: ledger)
        bridge = build_agent(cfg, shim, seed=seed, desk=desk)
        client_cfg = cfg.model_copy(deep=True)
        client_cfg.agent.name = cfg.agent.name + "_client"
        client = build_agent(client_cfg, shim)
        try:
            first = await local_dispatch_request(
                bridge,
                client,
                CallTool(tool=tool, args=replay_args({"request": "hello"})),
                CallToolResponse,
            )
            terms = parse_payment_terms(first.error)
            if terms is None:
                raise RuntimeError(f"expected payment terms, got: {first.error or first.result}")
            lines.append(f"price: {terms['amount']} testnet FET, payable to {terms['recipient']}")
            tx_hash = ledger.pay(
                payer=wallet_address(DEMO_BUYER_WALLET_SEED),
                recipient=terms["recipient"],
                amount_base=int(terms["amount_base"]),
                memo=terms["memo"],
            )
            lines.append(f"paid: transaction {short_tx(tx_hash)} with the quote as its memo")
            proof = {"reference": terms["reference"], "tx_hash": tx_hash}
            paid = await local_dispatch_request(
                bridge,
                client,
                CallTool(tool=tool, args=replay_args({"request": "hello"}, payment=proof)),
                CallToolResponse,
            )
            lines.append(f"answer: {paid.result if paid.result is not None else paid.error}")
            again = await local_dispatch_request(
                bridge,
                client,
                CallTool(tool=tool, args=replay_args({"request": "hello"}, payment=proof)),
                CallToolResponse,
            )
            lines.append(f"same payment again: {again.error}")
        finally:
            dispatcher.unregister(bridge.address, bridge)
            dispatcher.unregister(client.address, client)
            await desk.aclose()
    return lines
