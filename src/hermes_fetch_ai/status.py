"""``hermes-fetch-ai status``: what the agent is doing, in plain words.

Everything but the wallets and the testnet comes from this computer: the
records folder and the config. The wallets' balances and the testnet's newest
block come from Fetch's testnet ledger, unless ``--offline``.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from .background import LOG_FILE, read_running
from .config import BridgeConfig
from .ledger import LcdLedgerReader, LedgerUnavailable
from .money import format_fet
from .store import Store
from .wallet import BUYING_WALLET_INDEX, agent_address, wallet_address

_DAY_MS = 86_400_000
# A testnet block older than this means the chain has stopped (Dorado makes one every ~5 s).
STALE_BLOCK_SECONDS = 120


class ChainReader(Protocol):
    async def balance(self, address: str, denom: str) -> int: ...

    async def latest_block_ms(self) -> int: ...

    async def aclose(self) -> None: ...


def _ago(seconds: float) -> str:
    seconds = max(seconds, 0)
    if seconds < 90:
        return f"{seconds:.0f} seconds"
    if seconds < 90 * 60:
        return f"{seconds / 60:.0f} minutes"
    if seconds < 36 * 3600:
        return f"{seconds / 3600:.1f} hours"
    return f"{seconds / 86400:.1f} days"


def report(
    cfg: BridgeConfig,
    *,
    offline: bool = False,
    out: Callable[[str], None] = print,
    chain: Callable[[], ChainReader] | None = None,
    now: Callable[[], float] = time.time,
) -> int:
    """Print the agent's status; 0 if it is running, 3 if it is not."""
    from .uagent_app import payment_store_path

    state = cfg.payments.state_path
    running = read_running(state)
    seed = None if cfg.agent.dev_random_seed else cfg.effective_seed()
    if running is not None:
        out(f"Your agent is running: for {_ago(now() - running.started)} (process {running.pid}).")
    else:
        out("Your agent is not running. Start it: hermes fetchai-bridge start")
    if seed is not None:
        out(f"  Address:        {agent_address(seed)}")
    agent = cfg.agent
    if agent.mode == "mailbox":
        reach = "through its Agentverse mailbox, from anywhere"
        if agent.handle:
            reach += f"; ASI:One users can write to @{agent.handle}"
    elif agent.endpoint and ("127.0.0.1" in agent.endpoint or "localhost" in agent.endpoint):
        reach = "from this computer only"
    else:
        reach = f"at {agent.endpoint}" if agent.endpoint else "not set"
    out(f"  Reached:        {reach}")

    store = None
    records = payment_store_path(cfg, seed) if seed is not None else None
    if records is not None and records.exists():
        store = Store.open(records)
    try:
        _selling(cfg, store, now, out)
        _buying(cfg, store, now, out)
    finally:
        if store is not None:
            store.close()
    log = Path(running.log) if running is not None and running.log else state / LOG_FILE
    if log.exists():
        out(f"  Log:            {log}  (hermes fetchai-bridge logs)")
    if not offline and seed is not None:
        _chain(cfg, seed, chain, now, out)
    return 0 if running is not None else 3


def _selling(
    cfg: BridgeConfig, store: Store | None, now: Callable[[], float], out: Callable[[str], None]
) -> None:
    if not cfg.services:
        out("  Selling:        nothing (to sell services: hermes fetchai-bridge setup)")
        return
    prices = ", ".join(
        f"{name} {format_fet(svc.price_base)} FET" for name, svc in cfg.services.items()
    )
    paused = store is not None and store.paused()
    out(
        f"  Selling:        {prices}"
        + ("  (paused: hermes fetchai-bridge seller resume)" if paused else "")
    )
    if store is None:
        out("                  no sales yet")
        return
    count, earned = store.earned_since(int(now() * 1000) - _DAY_MS)
    out(f"                  {count} paid request(s) in the last day, {format_fet(earned)} test FET")
    failed = len(store.credits("failed"))
    if failed:
        out(
            f"                  {failed} paid request(s) failed after every retry; the buyers are owed "
            "refunds: hermes fetchai-bridge seller credits --status failed"
        )


def _buying(
    cfg: BridgeConfig, store: Store | None, now: Callable[[], float], out: Callable[[str], None]
) -> None:
    buying = cfg.buying
    if not buying.enabled:
        out("  Buying:         off")
        return
    spent = store.spent_since(int(now() * 1000) - _DAY_MS) if store is not None else 0
    out(
        f"  Buying:         on, up to {buying.max_payment} FET a payment and {buying.max_per_day} a day;"
        f" {format_fet(spent)} spent in the last day"
    )
    if store is None:
        return
    waiting = store.purchases("quoted")
    if waiting:
        out(
            f"                  {len(waiting)} payment request(s) waiting for your answer: "
            "hermes fetchai-bridge buyer purchases --status quoted"
        )
    unknown = store.purchases("needs_review")
    for purchase in unknown:
        out(
            f"                  payment {purchase.id} may or may not have gone through: "
            f"hermes fetchai-bridge buyer check {purchase.id}"
        )


def _chain(
    cfg: BridgeConfig,
    seed: str,
    chain: Callable[[], ChainReader] | None,
    now: Callable[[], float],
    out: Callable[[str], None],
) -> None:
    wallets = [("income", cfg.payments.payout_address or wallet_address(seed))]
    if cfg.buying.enabled:
        wallets.append(("buying", wallet_address(seed, BUYING_WALLET_INDEX)))

    async def ask() -> tuple[list[int], int]:
        reader = (
            chain()
            if chain is not None
            else LcdLedgerReader(cfg.payments.ledger_url, cfg.payments.ledger_timeout_seconds)
        )
        try:
            amounts = [await reader.balance(address, cfg.payments.denom) for _, address in wallets]
            return amounts, await reader.latest_block_ms()
        finally:
            await reader.aclose()

    try:
        amounts, newest_ms = asyncio.run(ask())
    except LedgerUnavailable as exc:
        out(f"  Testnet:        not answering ({exc}); balances unknown")
        return
    for (label, address), amount in zip(wallets, amounts, strict=True):
        out(f"  {label.capitalize() + ' wallet:':<16}{address}  {format_fet(amount)} test FET")
        if label == "buying" and amount == 0:
            out("                  empty; get free test FET: hermes fetchai-bridge wallet --fund")
    behind = now() - newest_ms / 1000
    if behind > STALE_BLOCK_SECONDS:
        out(
            f"  Testnet:        its newest block is {_ago(behind)} old; the chain may have stopped, so "
            "payments wait until it moves again"
        )
    else:
        out(f"  Testnet:        working (newest block {_ago(behind)} ago)")
