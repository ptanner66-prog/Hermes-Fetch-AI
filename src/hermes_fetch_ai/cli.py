from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from importlib import resources
from pathlib import Path

from pydantic import ValidationError

from .config import BridgeConfig, format_validation_error, load_config, validate_config_file
from .hermes_probe import probe
from .uagent_app import run_local_roundtrip
from .version_pins import check_pins

ROOT = Path(__file__).resolve().parents[2]
MAILBOX_GUIDE = (
    "https://github.com/ptanner66-prog/Hermes-Fetch-AI/blob/main/docs/agentverse-mailbox.md"
)


def example_config_path(name: str) -> Path:
    """Return an example config from a source checkout, else the packaged copy."""
    repo_example = ROOT / "examples" / name
    if repo_example.is_file():
        return repo_example
    packaged = Path(str(resources.files("hermes_fetch_ai").joinpath(f"data/{name}")))
    if packaged.is_file():
        return packaged
    raise FileNotFoundError(
        "no default config found; pass --config explicitly "
        f"(looked at {repo_example} and packaged data/{name})"
    )


def default_config_path() -> Path:
    return example_config_path("local-direct.yaml")


def _load_or_report(path: str | Path) -> BridgeConfig | None:
    try:
        return load_config(path)
    except ValidationError as exc:
        print(f"config: FAIL: {format_validation_error(exc)}", file=sys.stderr)
    except ValueError as exc:
        print(f"config: FAIL: {exc}", file=sys.stderr)
    return None


def doctor(args: argparse.Namespace) -> int:
    from . import __version__

    print(f"hermes-fetch-ai {__version__}")
    config_path = Path(args.config) if args.config else default_config_path()
    cfg = _load_or_report(config_path)
    if cfg is None:
        return 1
    note = "" if args.config else " (the demo config; pass --config to check yours)"
    print(f"config: ok: {config_path}{note}")
    pin_problems = check_pins()
    if pin_problems:
        print("pins: WARN: " + "; ".join(pin_problems))
    seed_warning = cfg.ignored_seed_warning()
    if seed_warning:
        print(f"seed: WARN: {seed_warning}")
    if cfg.payments.enabled:
        from .money import format_fet

        prices = ", ".join(
            f"{name} {format_fet(svc.price_base)} FET" for name, svc in cfg.services.items()
        )
        p = cfg.payments
        print(f"payments: on ({p.network}, {p.chain_id}); services: {prices or 'none'}")
        from .config import HermesRunnerConfig
        from .guest import describe

        for name, svc in cfg.services.items():
            if isinstance(svc.runner, HermesRunnerConfig):
                print(describe(cfg, name))
    else:
        print("payments: off")
    if not _programs_ok(cfg):
        return 1
    print("doctor: ok")
    return 0


def _programs_ok(cfg: BridgeConfig) -> bool:
    from .services import program_problems

    problems = program_problems(cfg)
    for problem in problems:
        print(f"services: FAIL: {problem}", file=sys.stderr)
    return not problems


def probe_hermes(args: argparse.Namespace) -> int:
    info = probe()
    for k, v in info.items():
        print(f"{k}: {v}")
    return 0 if info["hermes_tools_server"] == "importable" else 1


async def _demo_local() -> int:
    cfg = load_config(default_config_path())
    # The demo audits to a throwaway file, never to a real bridge's audit log.
    with tempfile.TemporaryDirectory(prefix="hermes-fetch-ai-demo-") as tmp:
        cfg.logging.audit_path = str(Path(tmp) / "audit.jsonl")
        bridge_address, visible_count, echo_result, audit_count = await run_local_roundtrip(cfg)
    print(f"bridge address: {bridge_address}")
    print(f"visible tool count: {visible_count}")
    print(f"echo result: {echo_result}")
    print(f"audit event count: {audit_count}")
    return 0 if echo_result == "hello" else 1


def demo(args: argparse.Namespace) -> int:
    if args.kind == "mailbox":
        ok, msg = validate_config_file(example_config_path("agentverse-mailbox.yaml"))
        if not ok:
            print(f"mailbox demo requires UAGENT_SEED and hosted mailbox setup: {msg}")
            print(f"setup guide: {MAILBOX_GUIDE}")
            return 1
        print(f"mailbox demo is a manual hosted setup; follow {MAILBOX_GUIDE}")
        return 0
    if args.kind == "paid":
        return _demo_paid()
    if args.kind == "chat":
        return _demo_chat()
    if args.kind == "buy":
        return _demo_buy()
    return asyncio.run(_demo_local())


def _demo_buy() -> int:
    from .buy_demo import run_buy_demo

    with tempfile.TemporaryDirectory(
        prefix="hermes-fetch-ai-buy-demo-", ignore_cleanup_errors=True
    ) as tmp:
        lines = asyncio.run(run_buy_demo(Path(tmp)))
    for line in lines:
        print(line)
    return 0 if lines[-1].endswith(": completed") else 1


def _demo_chat() -> int:
    from .chat_demo import run_chat_demo

    with tempfile.TemporaryDirectory(
        prefix="hermes-fetch-ai-chat-demo-", ignore_cleanup_errors=True
    ) as tmp:
        lines = asyncio.run(run_chat_demo(Path(tmp)))
    for line in lines:
        print(line)
    return 0 if any(line.startswith("seller says: tides") for line in lines) else 1


def _demo_paid() -> int:
    from .paid_demo import run_paid_demo

    with tempfile.TemporaryDirectory(
        prefix="hermes-fetch-ai-paid-demo-", ignore_cleanup_errors=True
    ) as tmp:
        lines = asyncio.run(run_paid_demo(Path(tmp)))
    for line in lines:
        print(line)
    return 0 if any(line.startswith("answer: hello") for line in lines) else 1


def _stable_seed(cfg: BridgeConfig, what: str) -> str | None:
    """The config's seed, or None (with a message) if it changes on every start."""
    if cfg.agent.dev_random_seed:
        print(
            f"{what}: FAIL: this config has agent.dev_random_seed: true, so the agent's "
            "identity and wallet change on every start; set it to false and set UAGENT_SEED",
            file=sys.stderr,
        )
        return None
    return cfg.effective_seed()


def wallet(args: argparse.Namespace) -> int:
    from .ledger import LcdLedgerReader, LedgerUnavailable
    from .money import format_fet
    from .wallet import BUYING_WALLET_INDEX, agent_address, wallet_address

    cfg = _load_or_report(args.config)
    if cfg is None:
        return 1
    seed = _stable_seed(cfg, "wallet")
    if seed is None:
        return 1
    income = cfg.payments.payout_address or wallet_address(seed)
    source = "payments.payout_address" if cfg.payments.payout_address else "the agent's own wallet"
    print(f"agent address: {agent_address(seed)}")
    print(f"income wallet: {income} ({source})")
    if args.fund and not cfg.buying.enabled:
        print(
            "wallet: FAIL: --fund fills the buying wallet; set buying.enabled: true",
            file=sys.stderr,
        )
        return 1
    wallets = [("balance", income)]
    if cfg.buying.enabled:
        buying = wallet_address(seed, BUYING_WALLET_INDEX)
        print(f"buying wallet: {buying} (pays other agents; it needs testnet FET)")
        wallets.append(("buying balance", buying))
        if args.fund and not _fund_from_faucet(buying):
            return 1
    if not args.balance:
        return 0

    async def balances() -> list[int]:
        reader = LcdLedgerReader(cfg.payments.ledger_url, cfg.payments.ledger_timeout_seconds)
        try:
            return [await reader.balance(address, cfg.payments.denom) for _, address in wallets]
        finally:
            await reader.aclose()

    try:
        amounts = asyncio.run(balances())
    except LedgerUnavailable as exc:
        print(f"balance: FAIL: {exc}", file=sys.stderr)
        return 1
    for (label, _), amount in zip(wallets, amounts, strict=True):
        print(f"{label}: {format_fet(amount)} testnet FET")
    return 0


def _fund_from_faucet(address: str) -> bool:
    """Ask Fetch's testnet faucet for free test FET for ``address``."""
    from cosmpy.aerial.config import NetworkConfig
    from cosmpy.aerial.faucet import FaucetApi

    print(f"asking Fetch's testnet faucet for test FET for {address} ...")
    try:
        FaucetApi(NetworkConfig.fetchai_stable_testnet()).get_wealth(address)
    except Exception as exc:  # noqa: BLE001 - any faucet failure gets the same advice
        print(f"wallet: FAIL: the faucet did not pay ({exc}); try again later", file=sys.stderr)
        return False
    print("faucet: done; the test FET can take a minute to arrive (check with --balance)")
    return True


def ledger(args: argparse.Namespace) -> int:
    from .ledger import LcdLedgerReader, LedgerUnavailable

    cfg = _load_or_report(args.config)
    if cfg is None:
        return 1
    payments = cfg.payments

    async def check() -> str:
        reader = LcdLedgerReader(payments.ledger_url, payments.ledger_timeout_seconds)
        try:
            return await reader.chain_id()
        finally:
            await reader.aclose()

    try:
        chain = asyncio.run(check())
    except LedgerUnavailable as exc:
        print(f"ledger: FAIL: {payments.ledger_url}: {exc}", file=sys.stderr)
        return 1
    if chain != payments.chain_id:
        print(
            f"ledger: FAIL: {payments.ledger_url} is {chain!r}, not {payments.chain_id!r}",
            file=sys.stderr,
        )
        return 1
    print(f"ledger: ok: {chain} at {payments.ledger_url}")
    return 0


def _try_service(cfg: BridgeConfig, name: str | None, request: str | None) -> int:
    """Run one service on this machine, unpaid, to check it works before selling it."""
    from .services import build_runner

    if not name or name not in cfg.services:
        known = ", ".join(cfg.services) or "none"
        print(f"seller: FAIL: try needs a service name (configured: {known})", file=sys.stderr)
        return 2
    if not request:
        print("seller: FAIL: try needs --request, what a buyer would ask", file=sys.stderr)
        return 2
    if not _programs_ok(cfg):
        return 1
    svc = cfg.services[name]
    result = asyncio.run(build_runner(cfg, name, show_errors=True).run(request))
    if not result.ok:
        print(f"seller: FAIL: {name}: {result.problem}", file=sys.stderr)
        return 1
    print(result.text.rstrip())
    if svc.disclaimer:
        print(f"\n— {svc.disclaimer}")
    return 0


def seller(args: argparse.Namespace) -> int:
    from .money import format_fet
    from .seller import short_tx
    from .store import Store
    from .uagent_app import payment_store_path

    cfg = _load_or_report(args.config)
    if cfg is None:
        return 1
    if not cfg.payments.enabled:
        print("seller: FAIL: payments are off in this config (payments.enabled)", file=sys.stderr)
        return 1
    if args.action == "try":
        return _try_service(cfg, args.target, args.request)
    if args.action in ("ban", "unban") and not args.target:
        print(f"seller: FAIL: {args.action} needs the agent address", file=sys.stderr)
        return 2
    if args.action == "backup" and not args.to:
        print("seller: FAIL: backup needs --to, the file to write", file=sys.stderr)
        return 2
    seed = _stable_seed(cfg, "seller")
    if seed is None:
        return 1
    store = Store.open(payment_store_path(cfg, seed))
    try:
        if args.action == "backup":
            try:
                store.backup(Path(args.to).expanduser())
            except (FileExistsError, OSError) as exc:
                print(f"seller: FAIL: {exc}", file=sys.stderr)
                return 1
            print(f"seller: payment records copied to {args.to}")
        elif args.action == "pause":
            store.set_paused(True)
            print("seller: paused; services are hidden and calls are refused until 'resume'")
        elif args.action == "resume":
            store.set_paused(False)
            print("seller: selling again")
        elif args.action == "ban":
            store.ban(args.target, reason=args.reason or "banned by the owner", now_ms=_now_ms())
            print(f"seller: {args.target} can no longer use your services")
        elif args.action == "unban":
            found = store.unban(args.target)
            print(f"seller: {args.target} " + ("unbanned" if found else "was not banned"))
        else:
            print(f"selling: {'paused' if store.paused() else 'on'}")
            now = _now_ms()
            store.lapse(older_than_ms=now - cfg.payments.redeem_window_seconds * 1000, now_ms=now)
            credits = store.credits(args.status)
            if not credits:
                print(
                    "no payments recorded" + (f" with status {args.status}" if args.status else "")
                )
            for credit in credits:
                print(
                    f"{credit.status:8} {format_fet(credit.amount_base):>10} FET  "
                    f"{credit.subject:20} tx {short_tx(credit.tx_hash)}  payer {credit.payer}"
                )
            for extra in store.extra_payments():
                print(
                    f"extra payment, refund it: {format_fet(extra.amount_base)} FET  "
                    f"tx {short_tx(extra.tx_hash)}  payer {extra.payer}"
                )
            for sender, reason in store.banned():
                print(f"banned: {sender} ({reason})")
    finally:
        store.close()
    return 0


def agentverse(args: argparse.Namespace) -> int:
    """List the bridge on Agentverse (an explicit, owner-run step)."""
    import os

    from uagents_core.utils.registration import AgentverseRequestError

    from .agentverse import API_KEY_VAR, register, registration
    from .wallet import agent_address

    cfg = _load_or_report(args.config)
    if cfg is None:
        return 1
    if not cfg.chat.enable_chat:
        print(
            "agentverse: FAIL: ASI:One talks to agents through chat; "
            "set chat.enable_chat: true (it sells the services in this config)",
            file=sys.stderr,
        )
        return 1
    seed = _stable_seed(cfg, "agentverse")
    if seed is None:
        return 1
    api_key = os.environ.get(API_KEY_VAR, "").strip()
    if not api_key:
        print(
            f"agentverse: FAIL: set {API_KEY_VAR} to an Agentverse API key with write "
            "access (agentverse.ai, Profile, API Keys)",
            file=sys.stderr,
        )
        return 1
    try:
        request = registration(cfg)
    except ValueError as exc:
        print(f"agentverse: FAIL: {exc}", file=sys.stderr)
        return 1
    address = agent_address(seed)
    if not args.yes:
        if not sys.stdin.isatty():
            print("agentverse: FAIL: confirm with --yes when not at a terminal", file=sys.stderr)
            return 2
        print(
            f"This lists {request.name} ({address}) publicly on Agentverse, where ASI:One "
            "users can find it. Agentverse keeps the listing."
        )
        if input("Continue? [y/N] ").strip().lower() not in ("y", "yes"):
            print("agentverse: nothing was registered")
            return 1
    try:
        register(cfg, seed, api_key)
    except (AgentverseRequestError, OSError, ValueError) as exc:
        print(f"agentverse: FAIL: {exc}", file=sys.stderr)
        return 1
    reach = f"@{request.handle}" if request.handle else f"@{address}"
    print(f"agentverse: listed {request.name} as a {request.type} agent ({address})")
    print(f"agentverse: start it with `serve`; in ASI:One, write to {reach}")
    return 0


def _now_ms() -> int:
    import time

    return int(time.time() * 1000)


def serve(args: argparse.Namespace) -> int:
    from .mcp_shim import HermesBackendError
    from .uagent_app import ServeError, run_bridge

    cfg = _load_or_report(args.config)
    if cfg is None:
        return 1
    seed_warning = cfg.ignored_seed_warning()
    if seed_warning:
        print(f"seed: WARN: {seed_warning}", file=sys.stderr)
    if not _programs_ok(cfg):
        return 1
    try:
        run_bridge(cfg)
    except HermesBackendError as exc:
        print(f"hermes backend: FAIL: {exc}", file=sys.stderr)
        return 1
    except ServeError as exc:
        print(f"serve: FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    from . import __version__

    p = argparse.ArgumentParser(prog="hermes-fetch-ai")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("doctor", help="check a config file and the installed dependency pins")
    d.add_argument("--config", default=None, help="config to check (default: the demo config)")
    d.set_defaults(func=doctor)
    ph = sub.add_parser("probe-hermes", help="check that Hermes' tools MCP server can be imported")
    ph.set_defaults(func=probe_hermes)
    s = sub.add_parser("serve", help="run the bridge uAgent until interrupted")
    s.add_argument("--config", required=True)
    s.set_defaults(func=serve)
    dm = sub.add_parser(
        "demo",
        help="run the local, paid, chat, or buy demo (offline), or check the mailbox setup",
    )
    dm.add_argument("kind", choices=["local", "paid", "chat", "buy", "mailbox"])
    dm.set_defaults(func=demo)
    w = sub.add_parser("wallet", help="show the agent's address and income wallet")
    w.add_argument("--config", required=True)
    w.add_argument("--balance", action="store_true", help="also ask the ledger for the balance")
    w.add_argument(
        "--fund",
        action="store_true",
        help="get free test FET for the buying wallet from Fetch's testnet faucet",
    )
    w.set_defaults(func=wallet)
    lg = sub.add_parser("ledger", help="check that the configured ledger answers as testnet")
    lg.add_argument("--config", required=True)
    lg.set_defaults(func=ledger)
    sl = sub.add_parser(
        "seller", help="see payments, try a service, pause selling, ban an agent, or back up"
    )
    sl.add_argument(
        "action", choices=["credits", "try", "pause", "resume", "ban", "unban", "backup"]
    )
    sl.add_argument(
        "target", nargs="?", help="the service name (try) or the agent address (ban, unban)"
    )
    sl.add_argument("--config", required=True)
    sl.add_argument("--status", default=None, help="only payments with this status (credits)")
    sl.add_argument("--reason", default=None, help="why, for ban")
    sl.add_argument("--request", default=None, help="what a buyer would ask, for try")
    sl.add_argument(
        "--to", default=None, help="the new file to copy payment records to, for backup"
    )
    sl.set_defaults(func=seller)
    av = sub.add_parser("agentverse", help="list the bridge on Agentverse for ASI:One users")
    av.add_argument("action", choices=["register"])
    av.add_argument("--config", required=True)
    av.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    av.set_defaults(func=agentverse)
    from .buyer_cli import add_parser as add_buyer_parser

    add_buyer_parser(sub)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
