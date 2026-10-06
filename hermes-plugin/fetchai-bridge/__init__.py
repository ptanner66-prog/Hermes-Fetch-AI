"""Hermes plugin for the Fetch.ai uAgents bridge (hermes-fetch-ai).

The bridge pins its own dependencies (uAgents, mcp 1.x) and runs on Python
3.11/3.12, so it cannot share Hermes' environment. This plugin is a thin,
stdlib-only wrapper declared with ``python_runtime: external``:

- ``hermes fetchai-bridge <args>`` runs the separately installed
  ``hermes-fetch-ai`` command with the same arguments;
- the bundled ``operate`` skill tells the agent how to use the bridge.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

PLUGIN_NAME = "fetchai-bridge"
BRIDGE_COMMAND = "hermes-fetch-ai"
INSTALL_HINT = (
    "uv tool install --python 3.12 "
    '"hermes-fetch-ai @ git+https://github.com/ptanner66-prog/Hermes-Fetch-AI"'
)
# How long a Ctrl-C'd bridge gets to finish its own graceful shutdown.
SHUTDOWN_GRACE_SECONDS = 30.0
# Hermes runs inside its own Python environment and exports variables that point
# any Python child at Hermes' packages (PYTHONPATH includes its checkout and
# site-packages). The bridge has its own interpreter, so these must not leak in.
HERMES_PYTHON_ENV = (
    "PYTHONPATH",
    "PYTHONHOME",
    "PYTHONEXECUTABLE",
    "__PYVENV_LAUNCHER__",
    "VIRTUAL_ENV",
)
# Instead, tell the bridge how this Hermes runs Python, so `serve` can start
# Hermes' tools MCP server the way Hermes itself does: with its own interpreter
# and import path. Names shared with hermes_fetch_ai.config.
HERMES_PYTHON_VAR = "HERMES_FETCH_AI_HERMES_PYTHON"
HERMES_PYTHONPATH_VAR = "HERMES_FETCH_AI_HERMES_PYTHONPATH"

_SKILLS_DIR = Path(__file__).resolve().parent / "skills"
_DESCRIPTION = """\
Run the Fetch.ai uAgents bridge. Arguments are passed unchanged to the
separately installed hermes-fetch-ai command, for example:

  hermes fetchai-bridge doctor
  hermes fetchai-bridge demo local
  hermes fetchai-bridge serve --config /absolute/path/to/bridge.yaml
  hermes fetchai-bridge probe-hermes
"""


def resolve_bridge_command(configured: str = "") -> str | None:
    """Return the bridge executable: the configured path or name, else hermes-fetch-ai on PATH."""
    return shutil.which(configured.strip() or BRIDGE_COMMAND)


def bridge_environment(
    environ: Mapping[str, str] | None = None, hermes_python: str | None = None
) -> dict[str, str]:
    """The caller's environment for the bridge: Hermes' Python settings are moved
    out of the way and handed over under the bridge's own variable names."""
    env = dict(os.environ if environ is None else environ)
    hermes_pythonpath = env.get("PYTHONPATH", "")
    for name in HERMES_PYTHON_ENV:
        env.pop(name, None)
    env[HERMES_PYTHON_VAR] = hermes_python or sys.executable
    if hermes_pythonpath:
        env[HERMES_PYTHONPATH_VAR] = hermes_pythonpath
    else:
        env.pop(HERMES_PYTHONPATH_VAR, None)
    return env


def run_bridge(argv: list[str], configured: str = "") -> int:
    """Run the bridge CLI with ``argv`` and return its exit status."""
    command = resolve_bridge_command(configured)
    if command is None:
        target = configured.strip() or BRIDGE_COMMAND
        print(
            f"{PLUGIN_NAME}: {target!r} not found. Install the bridge in its own environment:\n"
            f"  {INSTALL_HINT}\n"
            f"or set plugins.entries.{PLUGIN_NAME}.settings.command to its path.",
            file=sys.stderr,
        )
        return 1
    # The user ran this command explicitly. Like any command started from a shell,
    # the bridge inherits the environment, including UAGENT_SEED from Hermes' .env.
    process = subprocess.Popen([command, *argv], env=bridge_environment())
    try:
        return process.wait()
    except KeyboardInterrupt:
        # Ctrl-C reaches the bridge too; let it finish its graceful shutdown.
        try:
            return process.wait(timeout=SHUTDOWN_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            return process.wait()


def _setup_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "bridge_args",
        nargs=argparse.REMAINDER,
        metavar="ARGS",
        help="arguments for hermes-fetch-ai (start with: doctor)",
    )


def _register_skills(ctx: Any) -> None:
    register_skill = getattr(ctx, "register_skill", None)
    if register_skill is None:  # Hermes releases that predate plugin skills
        return
    for skill_md in sorted(_SKILLS_DIR.glob("*/SKILL.md")):
        register_skill(skill_md.parent.name, skill_md)


def register(ctx: Any) -> None:
    get_config = getattr(ctx, "get_config", None)
    configured = str(get_config("command", default="") or "") if get_config else ""

    def handle(args: argparse.Namespace) -> int:
        return run_bridge(list(args.bridge_args) or ["--help"], configured)

    ctx.register_cli_command(
        name=PLUGIN_NAME,
        help="Run the Fetch.ai uAgents bridge (hermes-fetch-ai)",
        setup_fn=_setup_parser,
        handler_fn=handle,
        description=_DESCRIPTION,
    )
    _register_skills(ctx)
