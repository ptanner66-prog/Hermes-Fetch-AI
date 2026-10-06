"""Answers like ``hermes chat --format stream-json``, steered by the request.

A request ending in ``fake:<mode>`` picks what happens; ``fake:record``
answers with a JSON description of how the bridge ran it.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any


def emit(event: dict[str, Any]) -> None:
    print(json.dumps({**event, "timestamp": int(time.time() * 1000)}), flush=True)


def result(text: str, exit_code: int = 0, **extra: Any) -> None:
    emit({"type": "result", "session_id": "fake", "exit_code": exit_code, "text": text, **extra})


def main() -> int:
    query = sys.stdin.read()
    mode = query.rsplit("fake:", 1)[1].split()[0] if "fake:" in query else "answer"
    home = Path(os.environ.get("HERMES_HOME", "."))
    emit({"type": "system", "subtype": "init", "model": "fake", "session_id": "fake"})
    if mode == "record":
        keys = home / ".env"
        result(
            json.dumps(
                {
                    "argv": sys.argv[1:],
                    "env": sorted(os.environ),
                    "home": str(home),
                    "user_home": os.environ.get("HOME"),
                    "cwd": os.getcwd(),
                    "files": sorted(p.name for p in home.iterdir()),
                    "settings": (home / "config.yaml").read_text(),
                    "keys": keys.read_text(),
                    "keys_mode": oct(keys.stat().st_mode & 0o777),
                    "query": query,
                }
            )
        )
    elif mode == "noise":
        print("  ! a plain warning line among the JSON lines", flush=True)
        print("{not json", flush=True)
        emit({"type": "text", "text": "thinking out loud"})
        result("an answer after some noise")
    elif mode == "no-result":
        print("It looks like Hermes isn't configured yet", flush=True)
    elif mode == "failed":
        result("", exit_code=1, error="the model server returned 500")
    elif mode == "error-field":
        result("partial words", error="Interrupted")
    elif mode == "empty":
        result("   ")
    elif mode == "exit-1":
        result("an answer")
        return 1
    elif mode == "long":
        result("y" * 5000)
    elif mode == "flood":
        while True:
            emit({"type": "tool_result", "output": "z" * 4096})
    elif mode == "hang":
        time.sleep(60)
    else:
        result("the answer")
    return 0


if __name__ == "__main__":
    sys.exit(main())
