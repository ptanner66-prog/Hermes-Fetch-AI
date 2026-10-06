"""Sending testnet FET from the buying wallet.

The transaction is built and signed first, and its hash is handed to the
caller before anything is broadcast. A payment whose outcome is unclear (the
connection drops mid-broadcast, the ledger is slow to include it) can then
always be looked up on the ledger later, rather than guessed at or sent twice.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from .config import PaymentsConfig
from .logging import get_logger

logger = get_logger("hermes_fetch_ai")

# Fetch's testnet gas price, in atestfet (cosmpy's own Dorado setting).
TESTNET_GAS_PRICE = 5_000_000_000
# How long to wait for a broadcast transaction to be included in a block.
INCLUSION_WAIT_SECONDS = 60.0

SendStatus = Literal["included", "rejected", "unknown"]


@dataclass(frozen=True)
class SendOutcome:
    # included: in a block and successful; rejected: nothing was transferred;
    # unknown: it may or may not have been transferred, so look it up.
    status: SendStatus
    tx_hash: str = ""
    problem: str = ""


class PaymentSender(Protocol):
    def address(self) -> str:
        """The wallet the payments come from (fetch1...)."""
        ...

    async def send(
        self,
        *,
        recipient: str,
        amount_base: int,
        memo: str,
        before_broadcast: Callable[[str], None],
    ) -> SendOutcome:
        """Pay ``amount_base`` atestfet to ``recipient``.

        ``before_broadcast`` gets the transaction hash before the transaction
        leaves this machine; if it raises, nothing is broadcast.
        """
        ...


def tx_hash_of(tx_bytes: bytes) -> str:
    """A Cosmos transaction's hash: SHA-256 of its signed bytes, in upper-case hex."""
    return hashlib.sha256(tx_bytes).hexdigest().upper()


class CosmpySender:
    """Sends from a cosmpy wallet through the ledger's REST endpoint.

    cosmpy is blocking, so each payment runs on one worker thread; payments
    are sent one at a time so the wallet's sequence numbers never collide.
    """

    def __init__(
        self,
        wallet: Any,
        payments: PaymentsConfig,
        *,
        inclusion_wait_seconds: float = INCLUSION_WAIT_SECONDS,
    ) -> None:
        self._wallet = wallet
        self._payments = payments
        self._inclusion_wait = inclusion_wait_seconds
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="fet-sender")
        self._lock = asyncio.Lock()

    def address(self) -> str:
        return str(self._wallet.address())

    def _client(self) -> Any:
        from cosmpy.aerial.client import LedgerClient, NetworkConfig

        return LedgerClient(
            NetworkConfig(
                chain_id=self._payments.chain_id,
                url="rest+" + self._payments.ledger_url,
                fee_minimum_gas_price=TESTNET_GAS_PRICE,
                fee_denomination=self._payments.denom,
                staking_denomination=self._payments.denom,
            )
        )

    async def send(
        self,
        *,
        recipient: str,
        amount_base: int,
        memo: str,
        before_broadcast: Callable[[str], None],
    ) -> SendOutcome:
        loop = asyncio.get_running_loop()
        async with self._lock:
            prepared = await loop.run_in_executor(
                self._executor, self._prepare, recipient, amount_base, memo
            )
            if isinstance(prepared, SendOutcome):
                return prepared
            client, tx, tx_hash = prepared
            # On the event loop's thread, like every other write to the records.
            before_broadcast(tx_hash)
            return await loop.run_in_executor(self._executor, self._broadcast, client, tx, tx_hash)

    def _prepare(
        self, recipient: str, amount_base: int, memo: str
    ) -> SendOutcome | tuple[Any, Any, str]:
        """Build and sign the payment; nothing leaves this machine yet."""
        from cosmpy.aerial.client.utils import prepare_basic_transaction
        from cosmpy.aerial.tx import Transaction
        from cosmpy.protos.cosmos.bank.v1beta1.tx_pb2 import MsgSend
        from cosmpy.protos.cosmos.base.v1beta1.coin_pb2 import Coin

        try:
            client = self._client()
            tx = Transaction()
            tx.add_message(
                MsgSend(
                    from_address=self.address(),
                    to_address=recipient,
                    amount=[Coin(amount=str(amount_base), denom=self._payments.denom)],
                )
            )
            tx = prepare_basic_transaction(client, tx, self._wallet, memo=memo)
            tx_bytes = tx.tx.SerializeToString()
        except Exception as exc:  # noqa: BLE001 - any failure here means nothing was sent
            logger.warning("payment not sent: could not prepare it (%s)", exc)
            return SendOutcome("rejected", problem=f"could not prepare the payment: {exc}")
        return client, tx, tx_hash_of(tx_bytes)

    def _broadcast(self, client: Any, tx: Any, tx_hash: str) -> SendOutcome:
        from cosmpy.aerial.exceptions import BroadcastError

        try:
            submitted = client.broadcast_tx(tx)
        except BroadcastError as exc:
            # The node refused it at the door: it never entered a block.
            return SendOutcome("rejected", tx_hash, f"the ledger refused the payment: {exc}")
        except Exception as exc:  # noqa: BLE001 - it may have arrived; never assume it did not
            logger.warning("payment %s: broadcast outcome unknown (%s)", tx_hash[:12], exc)
            return SendOutcome("unknown", tx_hash, f"the broadcast may not have arrived: {exc}")
        if str(submitted.tx_hash).upper() != tx_hash:
            logger.warning("payment %s: the ledger reported another hash", tx_hash[:12])
            tx_hash = str(submitted.tx_hash).upper()
        try:
            submitted.wait_to_complete(timeout=self._inclusion_wait, poll_period=2.0)
        except BroadcastError as exc:
            # Included but failed: fees were spent, nothing was transferred.
            return SendOutcome("rejected", tx_hash, f"the payment failed on the ledger: {exc}")
        except Exception as exc:  # noqa: BLE001 - it may still be included; look it up later
            logger.warning("payment %s: not seen on the ledger yet (%s)", tx_hash[:12], exc)
            return SendOutcome("unknown", tx_hash, "the payment was not seen on the ledger in time")
        return SendOutcome("included", tx_hash)

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
