"""FET amounts as exact integers of the chain's smallest unit.

1 FET is 10**18 base units (``afet`` on mainnet, ``atestfet`` on testnet).
Amounts are parsed from decimal strings and never pass through floats, so a
price of "0.1" is exactly 100000000000000000 base units.
"""

from __future__ import annotations

import re

FET_DECIMALS = 18
BASE_PER_FET: int = 10**18
# Prices above this are refused; a typo should not ask for a fortune.
MAX_PRICE_BASE: int = 1000 * BASE_PER_FET
_AMOUNT_RE = re.compile(r"(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,18})?")


def parse_fet(text: str) -> int:
    """Return the base-unit integer for a decimal FET amount such as "0.05".

    Rejects floats, signs, exponents, separators, surrounding spaces, and
    more than 18 decimal places.
    """
    if not isinstance(text, str) or not _AMOUNT_RE.fullmatch(text):
        raise ValueError(
            f'{text!r} is not a FET amount (write it as a string such as "0.05", '
            "with at most 18 decimal places)"
        )
    whole, _, fraction = text.partition(".")
    return int(whole) * BASE_PER_FET + int(fraction.ljust(FET_DECIMALS, "0"))


def format_fet(base: int) -> str:
    """Return a decimal FET string for ``base`` units, without trailing zeros."""
    if base < 0:
        raise ValueError("amounts are never negative")
    whole, fraction = divmod(base, BASE_PER_FET)
    if not fraction:
        return str(whole)
    return f"{whole}.{str(fraction).rjust(FET_DECIMALS, '0').rstrip('0')}"
