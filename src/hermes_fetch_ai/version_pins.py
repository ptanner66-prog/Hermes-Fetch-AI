from __future__ import annotations

from importlib import metadata

PINS = {
    "uagents": "0.24.2",
    "uagents-core": "0.4.4",
    "uagents-adapter": "0.6.2",
    "mcp": "1.27.1",
}


def check_pins() -> list[str]:
    problems: list[str] = []
    for pkg, expected in PINS.items():
        try:
            got = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            problems.append(f"{pkg} is not installed")
            continue
        if got != expected:
            problems.append(f"{pkg}=={got}, expected {expected}")
    return problems
