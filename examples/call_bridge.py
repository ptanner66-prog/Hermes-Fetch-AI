"""Call a running bridge from another uAgent: list its tools, then call one.

Start a bridge with fake tools (no Hermes, no secrets) and note the address it logs:

    hermes-fetch-ai serve --config examples/local-direct.yaml
    # INFO: [hermes_fetch_local]: Starting agent with address: agent1q...

Then, in another terminal:

    python examples/call_bridge.py agent1q... http://127.0.0.1:8001/submit

Against a Hermes-backed bridge, call a tool it exposes, such as skills_list
with no arguments. Without HERMES_FETCH_PAYER_SEED the client signs with a
throwaway identity, so the bridge sees an unknown sender and offers only its
public tools.

Paid services (docs/payments.md): call one with --request and the bridge
answers with its price. To pay on Fetch's testnet and get the answer, set
HERMES_FETCH_PAYER_SEED to a seed whose wallet holds testnet FET (the script
prints that wallet's address) and add --pay:

    python examples/call_bridge.py agent1q... http://127.0.0.1:8001/submit \\
        --tool service.research --request "tides in the Bay of Fundy" --pay
"""

from __future__ import annotations

import argparse
import asyncio
import os
from typing import Any

from uagents.communication import send_sync_message
from uagents.crypto import Identity
from uagents.resolver import RulesBasedResolver
from uagents_adapter.mcp.protocol import CallTool, CallToolResponse, ListTools, ListToolsResponse

from hermes_fetch_ai.direct_protocol import replay_args
from hermes_fetch_ai.money import parse_fet
from hermes_fetch_ai.seller import parse_payment_terms
from hermes_fetch_ai.wallet import wallet_address, wallet_for

PAYER_SEED_VAR = "HERMES_FETCH_PAYER_SEED"


def pay(terms: dict[str, Any], seed: str, max_fet: str) -> str:
    """Send the quoted testnet FET with the reference as the memo; return the hash."""
    from cosmpy.aerial.client import LedgerClient, NetworkConfig
    from cosmpy.crypto.address import Address

    if (terms["network"], terms["chain_id"], terms["denom"]) != ("testnet", "dorado-1", "atestfet"):
        raise SystemExit("refusing to pay: this example pays on Fetch's testnet (dorado-1) only")
    amount = int(terms["amount_base"])
    if amount > parse_fet(max_fet):
        raise SystemExit(f"refusing to pay {terms['amount']} FET: more than --max-fet {max_fet}")
    ledger = LedgerClient(NetworkConfig.fetchai_stable_testnet())
    tx = ledger.send_tokens(
        Address(terms["recipient"]), amount, terms["denom"], wallet_for(seed), memo=terms["memo"]
    )
    tx.wait_to_complete()  # raises if the transaction failed
    return str(tx.tx_hash)


async def main(
    address: str, endpoint: str, tool: str, args: dict[str, Any], pay_ok: bool, max_fet: str
) -> None:
    # Reach the bridge at a known endpoint instead of looking it up in the Almanac.
    resolver = RulesBasedResolver({address: endpoint})
    seed = os.environ.get(PAYER_SEED_VAR)
    if pay_ok and not seed:
        raise SystemExit(f"--pay needs {PAYER_SEED_VAR}: a seed whose testnet wallet holds FET")
    # A price quote is bound to the agent that asked, so paying needs one identity throughout.
    sender = Identity.from_seed(seed, 0) if seed else None
    if seed:
        print("paying from wallet:", wallet_address(seed))

    listed = await send_sync_message(
        address,
        ListTools(),
        response_type=ListToolsResponse,
        sender=sender,
        resolver=resolver,
        timeout=20,
    )
    if not isinstance(listed, ListToolsResponse):
        raise SystemExit(f"no ListTools response: {listed}")
    print("tools:", [t["name"] for t in listed.tools or []])

    async def call(payment: dict[str, str] | None = None) -> CallToolResponse:
        # Every call carries replay-protection metadata: a fresh request ID and issue time.
        called = await send_sync_message(
            address,
            CallTool(tool=tool, args=replay_args(args, payment=payment)),
            response_type=CallToolResponse,
            sender=sender,
            resolver=resolver,
            timeout=60,
        )
        if not isinstance(called, CallToolResponse):
            raise SystemExit(f"no CallTool response: {called}")
        return called

    called = await call()
    terms = parse_payment_terms(called.error)
    if terms is not None:
        print(f"price: {terms['amount']} testnet FET to {terms['recipient']}")
        if not pay_ok:
            print(f"to pay and get the answer, set {PAYER_SEED_VAR} and add --pay")
            return
        tx_hash = await asyncio.to_thread(pay, terms, seed or "", max_fet)
        print("paid in transaction:", tx_hash)
        proof = {"reference": terms["reference"], "tx_hash": tx_hash}
        # The bridge may not see the transaction for a few seconds.
        for delay in (0, 2, 4, 8, 16):
            await asyncio.sleep(delay)
            called = await call(proof)
            if not (called.error or "").startswith("payment pending"):
                break
    print("result:", called.result)
    print("error:", called.error)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("address", help="the bridge's agent address (agent1q...)")
    parser.add_argument("endpoint", help="for example http://127.0.0.1:8001/submit")
    parser.add_argument("--tool", default="echo")
    parser.add_argument("--text", default="hello", help="the text argument; '' sends no arguments")
    parser.add_argument("--request", help="for a paid service: what you want, in plain language")
    parser.add_argument("--pay", action="store_true", help="pay the quoted price on testnet")
    parser.add_argument("--max-fet", default="0.1", help="never pay more than this (default 0.1)")
    options = parser.parse_args()
    if options.request is not None:
        call_args: dict[str, Any] = {"request": options.request}
    else:
        call_args = {"text": options.text} if options.text else {}
    asyncio.run(
        main(
            options.address,
            options.endpoint,
            options.tool,
            call_args,
            options.pay,
            options.max_fet,
        )
    )
