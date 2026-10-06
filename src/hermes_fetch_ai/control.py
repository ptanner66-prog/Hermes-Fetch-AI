"""The control channel: how ``hermes-fetch-ai buyer ...`` reaches the running bridge.

Buying needs the running bridge: it is the agent other agents answer, and it
holds the buying wallet. While ``serve`` runs with buying enabled, it listens
on 127.0.0.1 only, on a random port, and writes the port and a random token to
``control.json`` in the bridge's state folder, readable only by the owner and
removed on shutdown. Each request is one line of JSON carrying the token;
anything else is refused. It is not HTTP, so a web page cannot talk to it.

The channel is a convenience for the owner and for Hermes' plugin, which run
as the same user; it is not a security boundary against that user. The
bridge's limits on buying (testnet only, approved amounts and recipients,
per-payment and daily caps) hold whoever asks.
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import math
import os
import secrets
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .buyer import MAX_REPLIES_AT_ONCE, Buyer, first_replies
from .config import BridgeConfig
from .logging import get_logger
from .money import format_fet, parse_fet
from .store import InboxEntry, Purchase, PurchaseRefused

logger = get_logger("hermes_fetch_ai")

CONTROL_FILE = "control.json"
# One request, and one answer, are each a line of JSON at most this long.
MAX_REQUEST_BYTES = 1024 * 1024
MAX_ANSWER_BYTES = 4 * 1024 * 1024
READ_TIMEOUT_SECONDS = 10.0
MAX_WAIT_SECONDS = 600.0
_DAY_MS = 86_400_000


class ControlError(Exception):
    """A control request could not be carried out; the message says why, for the owner."""


def control_path_in(state_dir: Path) -> Path:
    return state_dir / CONTROL_FILE


def control_path(cfg: BridgeConfig) -> Path:
    return control_path_in(cfg.payments.state_path)


def purchase_view(purchase: Purchase) -> dict[str, Any]:
    view = asdict(purchase)
    view["amount"] = format_fet(purchase.amount_base)
    view["amount_base"] = str(purchase.amount_base)
    return view


def entry_view(entry: InboxEntry) -> dict[str, Any]:
    return asdict(entry)


class ControlServer:
    """Serves the buyer's operations to local clients that know the token."""

    def __init__(self, buyer: Buyer, path: Path, *, agent_address: str) -> None:
        self.buyer = buyer
        self.path = path
        self.agent_address = agent_address
        self.token = secrets.token_hex(32)
        self._server: asyncio.Server | None = None

    async def start(self) -> None:
        if await _answers(self.path):
            raise ControlError(
                f"another bridge is already buying with the records in {self.path.parent}"
            )
        self._server = await asyncio.start_server(
            self._handle, "127.0.0.1", 0, limit=MAX_REQUEST_BYTES
        )
        port = self._server.sockets[0].getsockname()[1]
        _write_private(
            self.path,
            json.dumps(
                {
                    "port": port,
                    "token": self.token,
                    "pid": os.getpid(),
                    "agent": self.agent_address,
                }
            ),
        )

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            with contextlib.suppress(Exception):
                await self._server.wait_closed()
            self._server = None
        with contextlib.suppress(OSError, ValueError):
            if json.loads(self.path.read_text(encoding="utf-8")).get("token") == self.token:
                self.path.unlink()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            try:
                line = await asyncio.wait_for(reader.readline(), READ_TIMEOUT_SECONDS)
            except (TimeoutError, ValueError, asyncio.LimitOverrunError):
                return
            response = await self.answer(line)
            writer.write(json.dumps(response).encode("utf-8") + b"\n")
            with contextlib.suppress(ConnectionError):
                await writer.drain()
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def answer(self, line: bytes) -> dict[str, Any]:
        try:
            request = json.loads(line)
        except ValueError:
            return {"ok": False, "error": "not a JSON request"}
        if not isinstance(request, dict) or not hmac.compare_digest(
            str(request.get("token", "")), self.token
        ):
            return {"ok": False, "error": "not allowed"}
        op, args = request.get("op"), request.get("args") or {}
        if not isinstance(args, dict):
            return {"ok": False, "error": "args must be an object"}
        try:
            result = await self._run(str(op), args)
        except (PurchaseRefused, ControlError) as exc:
            return {"ok": False, "error": str(exc)}
        except (KeyError, TypeError, ValueError) as exc:
            return {"ok": False, "error": f"bad request: {exc}"}
        return {"ok": True, "result": result}

    def _wait(self, args: dict[str, Any]) -> float:
        """Seconds to wait for replies: the request's ``wait``, else the configured wait."""
        wait = float(args.get("wait", self.buyer.cfg.buying.reply_wait_seconds))
        if not (math.isfinite(wait) and wait >= 0):
            raise ValueError("wait must be a number of seconds")
        return min(wait, MAX_WAIT_SECONDS)

    async def _run(self, op: str, args: dict[str, Any]) -> Any:
        buyer = self.buyer
        store = buyer.store
        if op == "ping":
            return {"agent": self.agent_address}
        if op == "status":
            buying = buyer.cfg.buying
            now = buyer._now_ms()
            return {
                "agent": self.agent_address,
                "wallet": buyer.sender.address() if buyer.sender else None,
                "max_payment": buying.max_payment,
                "max_per_day": buying.max_per_day,
                "max_per_seller_per_day": buying.max_per_seller_per_day,
                "allowed_sellers": buying.allowed_sellers,
                "spent_last_24h": format_fet(store.spent_since(now - _DAY_MS)),
            }
        if op == "message":
            return await self._message(args)
        if op == "inbox":
            return await self._inbox(args)
        if op == "show":
            return purchase_view(buyer.show(str(args["id"])))
        if op == "pay":
            return await self._pay(args)
        if op == "decline":
            reason = str(args.get("reason") or "the owner declined")[:200]
            return purchase_view(await buyer.decline(str(args["id"]), reason))
        if op == "check":
            return purchase_view(await buyer.check(str(args["id"])))
        if op == "purchases":
            status = args.get("status")
            limit = min(int(args.get("limit", 50)), 200)
            return [purchase_view(p) for p in store.purchases(status, limit)]
        raise ControlError(f"unknown operation {op!r}")

    async def _message(self, args: dict[str, Any]) -> dict[str, Any]:
        to, wait = str(args["to"]), self._wait(args)
        session, mark = await self.buyer.message(to, str(args["text"]), args.get("session"))
        replies = await self.buyer.wait_for_reply(to, session, after_id=mark, timeout=wait)
        return {
            "session": session,
            "replies": [entry_view(e) for e in replies],
            "last_id": replies[-1].id if replies else mark,
        }

    async def _inbox(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        after = int(args.get("after", 0))
        peer, session = args.get("peer"), args.get("session")
        if args.get("wait"):
            if not (peer and session):
                raise ControlError("to wait for replies, give the agent and the conversation")
            entries = await self.buyer.wait_for_reply(
                str(peer), str(session), after_id=after, timeout=self._wait(args)
            )
        else:
            limit = min(int(args.get("limit", MAX_REPLIES_AT_ONCE)), MAX_REPLIES_AT_ONCE)
            entries = first_replies(
                self.buyer.store.inbox(peer=peer, session=session, after_id=after, limit=limit)
            )
        return [entry_view(e) for e in entries]

    async def _pay(self, args: dict[str, Any]) -> dict[str, Any]:
        """Pay an approved request, then wait for the seller's answer."""
        store = self.buyer.store
        purchase_id, wait = str(args["id"]), self._wait(args)
        mark = store.last_message_id()
        paid = await self.buyer.pay(
            purchase_id,
            nonce=str(args["code"]),
            expect_amount_base=parse_fet(str(args["amount"])),
            expect_recipient=str(args["recipient"]),
        )
        view = purchase_view(paid)
        replies: list[InboxEntry] = []
        if paid.status in ("paid", "committed", "completed"):
            # The seller answers once it has checked the payment and done the work;
            # its confirmation of the payment alone is not the answer.
            replies = await self.buyer.wait_for_reply(
                paid.peer,
                paid.session,
                after_id=mark,
                timeout=wait,
                answers=lambda entry: entry.kind != "payment_complete",
            )
            latest = store.purchase(purchase_id)
            if latest is not None:
                view["status"] = latest.status
        view["replies"] = [entry_view(e) for e in replies]
        view["last_id"] = replies[-1].id if replies else mark
        return view


def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def _read_control_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ControlError(
            "the bridge is not running with buying enabled; start it with "
            "`hermes-fetch-ai serve --config <your config>` (buying.enabled: true)"
        ) from None
    except (OSError, ValueError) as exc:
        raise ControlError(f"cannot read {path}: {exc}") from None
    if not isinstance(data, dict) or not {"port", "token"} <= set(data):
        raise ControlError(f"{path} is not a control file")
    return data


async def request(path: Path, op: str, args: dict[str, Any], *, timeout: float) -> Any:
    """Ask the running bridge to do ``op``; returns its result or raises ControlError."""
    data = _read_control_file(path)
    line = json.dumps({"token": data["token"], "op": op, "args": args}).encode("utf-8")
    if len(line) >= MAX_REQUEST_BYTES:
        raise ControlError("the request is too large for the bridge; send a shorter message")
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", int(data["port"]), limit=MAX_ANSWER_BYTES),
            5.0,
        )
    except (OSError, TimeoutError):
        raise ControlError(
            "the bridge is not answering; is `hermes-fetch-ai serve` still running?"
        ) from None
    try:
        writer.write(line + b"\n")
        await writer.drain()
        raw = await asyncio.wait_for(reader.readline(), timeout)
    except (OSError, TimeoutError, ValueError) as exc:
        raise ControlError(f"the bridge did not answer in time ({exc or 'timeout'})") from None
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()
    try:
        response = json.loads(raw)
    except ValueError:
        raise ControlError("the bridge sent an unreadable answer") from None
    if not response.get("ok"):
        raise ControlError(str(response.get("error") or "the bridge refused"))
    return response.get("result")


async def _answers(path: Path) -> bool:
    """True if a bridge is already serving the control channel described at ``path``."""
    try:
        await request(path, "ping", {}, timeout=2.0)
    except ControlError:
        return False
    return True
