from __future__ import annotations

import copy
import re
from typing import Any

REDACTED = "[REDACTED]"
_SENSITIVE_KV = re.compile(
    r"(?i)\b(seed|secret|token|api[_-]?key|password)(\s*[:=]\s*)"
    r"(\"[^\"]*\"|'[^']*'|[^,'\";}\]\r\n]+)"
)
_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", re.I),
    re.compile(r"\b[sp]k-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    re.compile(r"\b0x[a-fA-F0-9]{32,}\b"),
    re.compile(r"\b[a-fA-F0-9]{48,}\b"),
    re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b"),
]


def redact_text(s: str) -> str:
    out = str(s)
    out = _SENSITIVE_KV.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", out)
    for pat in _PATTERNS:
        out = pat.sub(REDACTED, out)
    return out


def redact_dict(d: Any) -> Any:
    if isinstance(d, dict):
        result = {}
        for k, v in d.items():
            if re.search(r"(?i)(seed|secret|token|api[_-]?key|password)", str(k)):
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
