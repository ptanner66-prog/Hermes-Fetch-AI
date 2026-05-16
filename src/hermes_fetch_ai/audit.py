from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from ._redaction import redact_text, short_sender

MAX_AUDIT_BYTES = 25 * 1024 * 1024
KEEP_FILES = 5
AUDIT_FIELDS = {
    "ts",
    "trace_id",
    "sender_short",
    "protocol",
    "msg_type",
    "tool",
    "decision",
    "reason",
    "duration_ms",
    "args_bytes",
    "output_bytes",
    "truncated",
    "error_class",
    "mode",
    "send_status",
}


class AuditWriter:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _rotate(self) -> None:
        if not self.path.exists() or self.path.stat().st_size < MAX_AUDIT_BYTES:
            return
        for idx in range(KEEP_FILES - 1, 0, -1):
            src = self.path.with_suffix(self.path.suffix + f".{idx}")
            dst = self.path.with_suffix(self.path.suffix + f".{idx + 1}")
            if src.exists():
                if idx + 1 > KEEP_FILES:
                    src.unlink(missing_ok=True)
                else:
                    src.replace(dst)
        self.path.replace(self.path.with_suffix(self.path.suffix + ".1"))

    def write(self, **event: Any) -> None:
        self._rotate()
        safe = {k: event.get(k) for k in AUDIT_FIELDS if k in event}
        safe.setdefault("ts", time.time())
        if "sender" in event:
            safe["sender_short"] = short_sender(str(event["sender"]))
        elif "sender_short" in safe:
            safe["sender_short"] = short_sender(str(safe["sender_short"]))
        line = redact_text(json.dumps(safe, sort_keys=True, default=str, ensure_ascii=False))
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def count(self) -> int:
        if not self.path.exists():
            return 0
        with self.path.open("r", encoding="utf-8") as f:
            return sum(1 for _ in f)


def default_audit_path() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "HermesFetchAI" / "audit.jsonl"
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "hermes-fetch-ai" / "audit.jsonl"
