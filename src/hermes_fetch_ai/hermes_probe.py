"""Report whether the bridge can start Hermes' tools MCP server."""

from __future__ import annotations

import importlib.util
import os
import subprocess
from importlib import metadata
from typing import Any

from .config import HERMES_PYTHON_VAR, HERMES_PYTHONPATH_VAR
from .fake_mcp import build_fake_server
from .mcp_shim import HERMES_TOOLS_MODULE, filtered_env
from .version_pins import check_pins

# Importing Hermes' tools server loads much of Hermes, which can take a while.
IMPORT_TIMEOUT_SECONDS = 60.0


def _importable_by(python: str, pythonpath: str | None) -> str:
    """Try importing the tools server with Hermes' interpreter, as `serve` would run it."""
    env = filtered_env()
    if pythonpath:
        env["PYTHONPATH"] = pythonpath
    try:
        result = subprocess.run(
            [python, "-c", f"import {HERMES_TOOLS_MODULE}"],
            env=env,
            capture_output=True,
            timeout=IMPORT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"not importable ({exc.__class__.__name__})"
    return "importable" if result.returncode == 0 else "not importable"


def _importable_here() -> str:
    try:
        spec = importlib.util.find_spec(HERMES_TOOLS_MODULE)
    except ModuleNotFoundError:
        spec = None
    return "importable" if spec else "not importable"


def probe() -> dict[str, Any]:
    """Versions, pins, and whether Hermes' tools server module can be imported.

    Through `hermes fetchai-bridge`, the check uses the interpreter the Hermes
    plugin hands over, which is the one `serve` starts the server with.
    Otherwise it checks the bridge's own interpreter, which only has Hermes
    when both are installed in one environment.
    """
    info: dict[str, Any] = {}
    for pkg in ("hermes-fetch-ai", "uagents", "mcp"):
        try:
            info[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            info[pkg] = "not installed"
    info["pins"] = "; ".join(check_pins()) or "ok"
    info["fake_tools"] = len(build_fake_server().tools)
    hermes_python = os.environ.get(HERMES_PYTHON_VAR)
    if hermes_python:
        info["hermes_python"] = hermes_python
        info["hermes_tools_server"] = _importable_by(
            hermes_python, os.environ.get(HERMES_PYTHONPATH_VAR)
        )
    else:
        info["hermes_python"] = "not handed over (run through `hermes fetchai-bridge`)"
        info["hermes_tools_server"] = _importable_here()
    return info
