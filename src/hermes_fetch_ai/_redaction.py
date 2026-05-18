from __future__ import annotations

import copy
import re
from typing import Any

REDACTED = "[REDACTED]"
_SECRET_KEY_RE = re.compile(
    r"(?i)(seed|secret|token|api[_-]?key|password|private[_-]?key|"
    r"recovery[_-]?phrase|mnemonic|mailbox[_-]?key|auth|credential|wallet)"
)
_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", re.I),
    re.compile(r"\b[sp]k-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    re.compile(
        r"(?i)(seed|secret|token|api[_-]?key|password|private[_-]?key|"
        r"recovery[_-]?phrase|mnemonic|mailbox[_-]?key|auth|credential|wallet)"
        r"\s*[:=]\s*['\"]?[^'\"\s,}]+"
    ),
    re.compile(r"\b0x[a-fA-F0-9]{32,}\b"),
    re.compile(r"\b[a-fA-F0-9]{48,}\b"),
    re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b"),
]


def _redact_key_value(match: re.Match[str]) -> str:
    text = match.group(0)
    separator = ":" if ":" in text and ("=" not in text or text.index(":") < text.index("=")) else "="
    return text.split(separator, 1)[0] + separator + REDACTED


def redact_text(s: str) -> str:
    out = str(s)
    for pat in _PATTERNS:
        if "api" in pat.pattern and "[:=]" in pat.pattern:
            out = pat.sub(_redact_key_value, out)
        else:
            out = pat.sub(REDACTED, out)
    return out


def redact_dict(d: Any) -> Any:
    if isinstance(d, dict):
        result = {}
        for k, v in d.items():
            if _SECRET_KEY_RE.search(str(k)):
                result[k] = REDACTED
            else:
                result[k] = redact_dict(v)
        return result
    if isinstance(d, list):
        return [redact_dict(v) for v in d]
    if isinstance(d, str):
        return redact_text(d)
    return copy.deepcopy(d)


def short_sender(address: str | None) -> str:
    if not address:
        return "unknown"
    if len(address) <= 16:
        return address
    return f"{address[:10]}…{address[-6:]}"
