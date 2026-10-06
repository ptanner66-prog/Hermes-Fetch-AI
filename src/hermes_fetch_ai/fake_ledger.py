"""An in-memory ledger for the offline paid demo and the tests.

It answers like the real one for the transactions it holds, so a payment can
be made and verified without any network.
"""

from __future__ import annotations

import hashlib
import itertools
import time
from collections.abc import Callable

from .ledger import Transfer, TxRecord
from .sender import SendOutcome

FAKE_CHAIN_ID = "dorado-1"


class FakeLedger:
    def __init__(self, chain_id: str = FAKE_CHAIN_ID) -> None:
        self._chain_id = chain_id
        self._txs: dict[str, TxRecord] = {}
        self._heights = itertools.count(1000)
        self.requests = 0

    async def chain_id(self) -> str:
        self.requests += 1
        return self._chain_id

    async def get_tx(self, tx_hash: str) -> TxRecord | None:
        self.requests += 1
        return self._txs.get(tx_hash.upper().removeprefix("0X"))

    async def balance(self, address: str, denom: str) -> int:
        self.requests += 1
        return sum(
            transfer.amount
            for tx in self._txs.values()
            if tx.code == 0
            for transfer in tx.transfers
            if transfer.recipient == address and transfer.denom == denom
        )

    async def aclose(self) -> None:
        return None

    def add(self, tx: TxRecord) -> TxRecord:
        self._txs[tx.hash] = tx
        return tx

    def pay(
        self,
        *,
        payer: str,
        recipient: str,
        amount_base: int,
        denom: str = "atestfet",
        memo: str = "",
        time_ms: int | None = None,
        code: int = 0,
    ) -> str:
        """Record a transfer and return its transaction hash."""
        height = next(self._heights)
        seed = f"{payer}|{recipient}|{amount_base}|{denom}|{memo}|{height}"
        tx_hash = hashlib.sha256(seed.encode("utf-8")).hexdigest().upper()
        self.add(
            TxRecord(
                hash=tx_hash,
                height=height,
                code=code,
                time_ms=int(time.time() * 1000) if time_ms is None else time_ms,
                memo=memo,
                transfers=(Transfer(payer, recipient, denom, amount_base),),
                other_messages=(),
            )
        )
        return tx_hash


class FakeSender:
    """Pays on a FakeLedger, for the offline demos and the tests.

    ``outcome`` picks what happens: "included" (paid), "rejected" (nothing
    sent), "unknown" (nothing known, nothing sent), or "lost" (the outcome is
    unknown to the sender, but the payment did reach the ledger).
    """

    def __init__(self, ledger: FakeLedger, address: str, *, outcome: str = "included") -> None:
        self.ledger = ledger
        self._address = address
        self.outcome = outcome
        self.sent: list[tuple[str, int, str]] = []
        self._count = itertools.count(1)

    def address(self) -> str:
        return self._address

    async def send(
        self,
        *,
        recipient: str,
        amount_base: int,
        memo: str,
        before_broadcast: Callable[[str], None],
    ) -> SendOutcome:
        seed = f"{self._address}|{recipient}|{amount_base}|{memo}|{next(self._count)}"
        tx_hash = hashlib.sha256(seed.encode("utf-8")).hexdigest().upper()
        before_broadcast(tx_hash)
        if self.outcome == "rejected":
            return SendOutcome("rejected", tx_hash, "the ledger refused the payment")
        if self.outcome in ("included", "lost"):
            self.sent.append((recipient, amount_base, memo))
            self.ledger.add(
                TxRecord(
                    hash=tx_hash,
                    height=next(self.ledger._heights),
                    code=0,
                    time_ms=int(time.time() * 1000),
                    memo=memo,
                    transfers=(Transfer(self._address, recipient, "atestfet", amount_base),),
                    other_messages=(),
                )
            )
        if self.outcome == "included":
            return SendOutcome("included", tx_hash)
        return SendOutcome("unknown", tx_hash, "the broadcast may not have arrived")
