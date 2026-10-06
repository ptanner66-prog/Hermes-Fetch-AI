"""Signed price quotes, so asking for a price stores nothing.

A quote's reference is a short token (about 80 characters, well inside the
256-character transaction memo limit) carrying the amount, its creation time,
validity, an optional amount tag and a random nonce. Its HMAC also covers
everything the token does not carry: the buyer's address, the service, a
digest of the exact request, and where the money must go. A flood of quote
requests therefore costs no storage, and a reference only works for the call
it was issued for.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import struct
from dataclasses import dataclass
from typing import Any, Literal

QuoteKind = Literal["call", "chat"]
PREFIX = "hfq1."
_KINDS: dict[str, int] = {"call": 0, "chat": 1}
_KIND_NAMES = {code: name for name, code in _KINDS.items()}
# version, kind, created_ms, ttl_seconds, amount (128-bit), tag, nonce
_PAYLOAD = struct.Struct(">BBQI16sH8s")
_MAC_BYTES = 16
_VERSION = 1


class QuoteError(ValueError):
    """The reference is malformed, forged, or belongs to a different call."""


@dataclass(frozen=True)
class Quote:
    kind: QuoteKind
    sender: str
    subject: str
    digest: str
    amount_base: int
    tag: int
    recipient: str
    denom: str
    chain_id: str
    created_ms: int
    ttl_seconds: int
    nonce: str

    @property
    def expires_ms(self) -> int:
        return self.created_ms + self.ttl_seconds * 1000


def quote_key(seed: str) -> bytes:
    """The HMAC key for quotes, derived from the agent's seed."""
    return hmac.new(seed.encode("utf-8"), b"hermes-fetch-ai quote key v1", hashlib.sha256).digest()


def request_digest(args: dict[str, Any]) -> str:
    """A stable digest of a call's arguments (key order does not matter)."""
    canonical = json.dumps(args, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _context(
    sender: str, subject: str, digest: str, recipient: str, denom: str, chain_id: str
) -> bytes:
    return json.dumps(
        [sender, subject, digest, recipient, denom, chain_id], separators=(",", ":")
    ).encode("utf-8")


def _mac(key: bytes, payload: bytes, context: bytes) -> bytes:
    return hmac.new(key, payload + b"\x00" + context, hashlib.sha256).digest()[:_MAC_BYTES]


def issue_quote(
    key: bytes,
    *,
    kind: QuoteKind,
    sender: str,
    subject: str,
    digest: str,
    amount_base: int,
    recipient: str,
    denom: str,
    chain_id: str,
    now_ms: int,
    ttl_seconds: int,
    tag: int = 0,
) -> tuple[Quote, str]:
    """Create a quote and its reference token."""
    if not 0 < amount_base < 2**128:
        raise ValueError("quoted amount out of range")
    if not 0 <= tag < 2**16:
        raise ValueError("tag out of range")
    nonce = secrets.token_bytes(8)
    payload = _PAYLOAD.pack(
        _VERSION, _KINDS[kind], now_ms, ttl_seconds, amount_base.to_bytes(16, "big"), tag, nonce
    )
    mac = _mac(key, payload, _context(sender, subject, digest, recipient, denom, chain_id))
    token = PREFIX + base64.urlsafe_b64encode(payload + mac).decode("ascii").rstrip("=")
    quote = Quote(
        kind=kind,
        sender=sender,
        subject=subject,
        digest=digest,
        amount_base=amount_base,
        tag=tag,
        recipient=recipient,
        denom=denom,
        chain_id=chain_id,
        created_ms=now_ms,
        ttl_seconds=ttl_seconds,
        nonce=nonce.hex(),
    )
    return quote, token


def open_quote(
    key: bytes,
    token: str,
    *,
    sender: str,
    subject: str,
    digest: str,
    recipient: str,
    denom: str,
    chain_id: str,
) -> Quote:
    """Check ``token`` against the call it is presented with and return its quote."""
    if not isinstance(token, str) or not token.startswith(PREFIX) or len(token) > 128:
        raise QuoteError("not a quote reference from this bridge")
    encoded = token[len(PREFIX) :]
    try:
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except ValueError:
        raise QuoteError("not a quote reference from this bridge") from None
    if len(raw) != _PAYLOAD.size + _MAC_BYTES:
        raise QuoteError("not a quote reference from this bridge")
    payload, mac = raw[: _PAYLOAD.size], raw[_PAYLOAD.size :]
    expected = _mac(key, payload, _context(sender, subject, digest, recipient, denom, chain_id))
    if not hmac.compare_digest(mac, expected):
        raise QuoteError("quote does not match this call")
    version, kind_code, created_ms, ttl_seconds, amount, tag, nonce = _PAYLOAD.unpack(payload)
    if version != _VERSION or kind_code not in _KIND_NAMES:
        raise QuoteError("not a quote reference from this bridge")
    kind: QuoteKind = "call" if _KIND_NAMES[kind_code] == "call" else "chat"
    return Quote(
        kind=kind,
        sender=sender,
        subject=subject,
        digest=digest,
        amount_base=int.from_bytes(amount, "big"),
        tag=tag,
        recipient=recipient,
        denom=denom,
        chain_id=chain_id,
        created_ms=created_ms,
        ttl_seconds=ttl_seconds,
        nonce=nonce.hex(),
    )
