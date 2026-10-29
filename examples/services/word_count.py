#!/usr/bin/env python3
"""A template for your own service program (the bridge's ``command`` runner).

For each paid request the bridge starts this program in an empty temporary
directory with a short environment (add variables with the service's
``pass_env``) and writes ``{"request": "<what the buyer asked>"}`` to its
stdin. What the program prints is the answer the buyer gets.

Exit 0 when the answer is ready. Exit non-zero if something on your side
failed: the buyer keeps the payment and can repeat the call. Text printed to
stderr never reaches the buyer.

Replace answer() with your own work; this one counts words.
"""

from __future__ import annotations

import json
import sys


def answer(request: str) -> str:
    words = len(request.split())
    return (
        f"Your text has {words} {'word' if words == 1 else 'words'} and {len(request)} characters."
    )


def main() -> int:
    request = json.load(sys.stdin)["request"]
    print(answer(request))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
