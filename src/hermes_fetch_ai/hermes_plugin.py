"""Hermes Agent plugin entry point.

Discovered through the ``hermes_agent.plugins`` entry-point group. Hermes
imports this module and calls :func:`register`, which attaches the bridge CLI
as ``hermes fetchai ...`` via the generic plugin surface — no Hermes core
files are touched, per the Hermes plugin policy.

Imports of the bridge runtime stay inside the handler so Hermes plugin
discovery never pays the uagents/mcp import cost at startup.
"""

from __future__ import annotations

from typing import Any

_HELP = "Fetch.ai uAgents bridge for Hermes tools"
_DESCRIPTION = (
    "Expose a policy-gated, default-deny subset of Hermes tools to Fetch.ai "
    "uAgents over the published MCP protocol."
)


def _setup_parser(subparser: Any) -> None:
    sub = subparser.add_subparsers(dest="fetchai_cmd", required=True)
    doctor = sub.add_parser("doctor", help="Validate bridge config and version pins")
    doctor.add_argument("--config", default=None)
    doctor.add_argument("--contamination-scan", action="store_true")
    sub.add_parser("probe", help="Probe local Hermes MCP seams for the bridge")
    serve = sub.add_parser("serve", help="Run the bridge uAgent")
    serve.add_argument("--config", required=True)
    demo = sub.add_parser("demo", help="Run the local two-uAgent round-trip demo")
    demo.add_argument("kind", choices=["local", "mailbox"], nargs="?", default="local")


def _handle(args: Any) -> int:
    from . import cli as bridge_cli

    cmd = getattr(args, "fetchai_cmd", None)
    if cmd == "doctor":
        argv = ["doctor"]
        if args.config:
            argv += ["--config", args.config]
        if args.contamination_scan:
            argv.append("--contamination-scan")
    elif cmd == "probe":
        argv = ["probe-hermes"]
    elif cmd == "serve":
        argv = ["serve", "--config", args.config]
    elif cmd == "demo":
        argv = ["demo", args.kind]
    else:
        return 2
    return bridge_cli.main(argv)


def register(ctx: Any) -> None:
    ctx.register_cli_command(
        name="fetchai",
        help=_HELP,
        setup_fn=_setup_parser,
        handler_fn=_handle,
        description=_DESCRIPTION,
    )
