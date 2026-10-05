"""Exact runtime pins this release was tested with.

The pins are read from the installed distribution's own ``Requires-Dist``
metadata, so they always match ``pyproject.toml`` and cannot drift when a
dependency bump only edits ``pyproject.toml``.
"""

from __future__ import annotations

import re
from importlib import metadata

DISTRIBUTION = "hermes-fetch-ai"

# Exact pins such as ``uagents==0.25.3`` or ``uagents-adapter[mcp]==0.6.2``.
# Ranges and optional extras (which carry an ``; extra == ...`` marker) are skipped.
_EXACT_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?==([^\s;,]+)$")


def declared_pins() -> dict[str, str]:
    """Return ``{distribution: version}`` for every exact runtime pin."""
    try:
        requirements = metadata.requires(DISTRIBUTION) or []
    except metadata.PackageNotFoundError:
        return {}
    pins: dict[str, str] = {}
    for requirement in requirements:
        match = _EXACT_PIN.match(requirement.strip())
        if match:
            pins[match.group(1).lower()] = match.group(2)
    return pins


def check_pins() -> list[str]:
    pins = declared_pins()
    if not pins:
        return [f"{DISTRIBUTION} is not installed; cannot read its tested dependency pins"]
    problems: list[str] = []
    for pkg, expected in sorted(pins.items()):
        try:
            got = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            problems.append(f"{pkg} is not installed")
            continue
        if got != expected:
            problems.append(f"{pkg}=={got}, expected {expected}")
    return problems
