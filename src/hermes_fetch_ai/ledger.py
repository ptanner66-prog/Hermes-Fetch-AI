"""Read Fetch ledger transactions for payment verification.

The bridge verifies payments itself instead of trusting the buyer, so it needs
the parts of a transaction that cosmpy's ``query_tx`` drops: the memo and the
decoded transfer messages. They come from the Cosmos REST API, read with
httpx, which has real timeouts and honours proxy and CA settings.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

import httpx

# httpx logs every request at INFO, wallet addresses in URLs included.
logging.getLogger("httpx").setLevel(logging.WARNING)

MSG_SEND = "/cosmos.bank.v1beta1.MsgSend"
_TX_HASH_RE = re.compile(r"[0-9A-F]{64}")
_DIGITS_RE = re.compile(r"[0-9]{1,40}")
# The REST endpoint sometimes answers with an empty body or a gateway error.
_RETRY_STATUSES = frozenset({502, 503, 504})
_RETRY_DELAYS = (0.25, 0.5, 1.0)


class LedgerUnavailable(Exception):
    """The ledger could not be read; the caller may try again later."""


@dataclass(frozen=True)
class Transfer:
    sender: str
    recipient: str
    denom: str
    amount: int


@dataclass(frozen=True)
class TxRecord:
    hash: str
    height: int
    code: int
    time_ms: int | None
    memo: str
    transfers: tuple[Transfer, ...]
    # Type URLs of every message that is not a plain MsgSend.
    other_messages: tuple[str, ...]


class LedgerReader(Protocol):
    async def chain_id(self) -> str: ...

    async def get_tx(self, tx_hash: str) -> TxRecord | None:
        """The transaction, or None if the ledger does not know it (yet)."""
        ...

    async def balance(self, address: str, denom: str) -> int: ...

    async def aclose(self) -> None: ...


def normalize_tx_hash(value: str) -> str:
    """Return ``value`` as 64 upper-case hex digits, or raise ValueError."""
    text = value.strip() if isinstance(value, str) else ""
    if text[:2] in ("0x", "0X"):
        text = text[2:]
    text = text.upper()
    if not _TX_HASH_RE.fullmatch(text):
        raise ValueError("a transaction hash is 64 hex digits")
    return text


def _time_ms(value: object) -> int | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return int(datetime.fromisoformat(value).timestamp() * 1000)
    except ValueError:
        return None


def _amount(value: object) -> int:
    if not isinstance(value, str) or not _DIGITS_RE.fullmatch(value):
        raise ValueError("malformed amount")
    return int(value)


def parse_tx(data: Any) -> TxRecord:
    """Build a TxRecord from a ``/cosmos/tx/v1beta1/txs/{hash}`` response."""
    try:
        response = data["tx_response"]
        body = data["tx"]["body"]
        transfers: list[Transfer] = []
        others: list[str] = []
        for message in body.get("messages", []):
            kind = str(message.get("@type", ""))
            if kind != MSG_SEND:
                others.append(kind)
                continue
            for coin in message.get("amount", []):
                transfers.append(
                    Transfer(
                        sender=str(message["from_address"]),
                        recipient=str(message["to_address"]),
                        denom=str(coin["denom"]),
                        amount=_amount(coin["amount"]),
                    )
                )
        memo = body.get("memo", "")
        return TxRecord(
            hash=normalize_tx_hash(str(response["txhash"])),
            height=int(response.get("height", 0)),
            code=int(response.get("code", 0)),
            time_ms=_time_ms(response.get("timestamp")),
            memo=memo if isinstance(memo, str) else "",
            transfers=tuple(transfers),
            other_messages=tuple(others),
        )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise LedgerUnavailable(f"malformed transaction from the ledger ({exc})") from None


class LcdLedgerReader:
    """A LedgerReader over a Cosmos REST ("LCD") endpoint."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
            headers={"Accept": "application/json"},
        )
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _get(self, path: str) -> tuple[int, Any]:
        """GET ``path`` within one overall deadline, retrying transient failures."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._timeout
        problem = "no answer"
        for delay in (*_RETRY_DELAYS, None):
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            try:
                response = await asyncio.wait_for(self._client.get(self._base + path), remaining)
            except (httpx.HTTPError, TimeoutError) as exc:
                problem = exc.__class__.__name__
            else:
                if response.status_code not in _RETRY_STATUSES and response.content:
                    try:
                        return response.status_code, response.json()
                    except ValueError:
                        problem = "a response that is not JSON"
                else:
                    problem = f"HTTP {response.status_code}"
            if delay is None or loop.time() + delay >= deadline:
                break
            await asyncio.sleep(delay)
        raise LedgerUnavailable(f"the ledger did not answer ({problem})")

    async def chain_id(self) -> str:
        status, body = await self._get("/cosmos/base/tendermint/v1beta1/node_info")
        try:
            network = body["default_node_info"]["network"]
        except (KeyError, TypeError):
            network = None
        if status != 200 or not isinstance(network, str):
            raise LedgerUnavailable(f"unexpected node_info response (HTTP {status})")
        return network

    async def get_tx(self, tx_hash: str) -> TxRecord | None:
        status, body = await self._get(f"/cosmos/tx/v1beta1/txs/{normalize_tx_hash(tx_hash)}")
        if status == 200:
            return parse_tx(body)
        message = body.get("message", "") if isinstance(body, dict) else ""
        if status == 404 or "not found" in str(message).lower():
            return None
        raise LedgerUnavailable(f"unexpected transaction response (HTTP {status})")

    async def balance(self, address: str, denom: str) -> int:
        status, body = await self._get(
            f"/cosmos/bank/v1beta1/balances/{address}/by_denom?denom={denom}"
        )
        try:
            if status != 200:
                raise ValueError(f"HTTP {status}")
            return _amount(body["balance"]["amount"])
        except (KeyError, TypeError, ValueError) as exc:
            raise LedgerUnavailable(f"unexpected balance response ({exc})") from None
