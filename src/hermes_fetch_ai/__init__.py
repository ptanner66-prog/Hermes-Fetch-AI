from __future__ import annotations

from importlib import metadata

try:
    __version__ = metadata.version("hermes-fetch-ai")
except metadata.PackageNotFoundError:  # uninstalled source tree
    __version__ = "0.0.0.dev0"
