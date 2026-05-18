from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from ._redaction import redact_text
from .audit import AuditWriter
from .config import load_config, validate_config_file
from .hermes_probe import probe
from .mcp_shim import HermesMCPClientShim
from .payments import PaymentDryRunStore, dryrun_transaction_id
from .uagent_app import run_bridge_for, run_local_roundtrip, run_local_tool_roundtrip
from .version_pins import check_pins

ROOT = Path(__file__).resolve().parents[2]


def _contamination_scan() -> tuple[bool, str]:
    forbidden = [
        "Open" + "Claw",
        "legal" + "-tech",
        "private " + "project",
        "domain-specific " + "guardrail",
        "private " + "key",
        "recovery " + "phrase",
        "mainnet " + "spend",
        "real FET " + "movement",
    ]
    paths = [
        ROOT / "src",
        ROOT / "docs",
        ROOT / "examples",
        ROOT / "README.md",
        ROOT / ".env.example",
        ROOT / "pyproject.toml",
    ]
    hits: list[str] = []
    for p in paths:
        files = [p] if p.is_file() else list(p.rglob("*")) if p.exists() else []
        for f in files:
            if not f.is_file() or f.suffix.lower() in {".pyc", ".png", ".jpg"}:
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
            for term in forbidden:
                if term.lower() in text.lower():
                    hits.append(f"{f}: {term}")
    return (not hits, "ok" if not hits else "\n".join(hits))


def doctor(args: argparse.Namespace) -> int:
    require_runtime_secrets = not (args.contamination_scan or args.probe_backend)
    ok, msg = validate_config_file(args.config, require_runtime_secrets=require_runtime_secrets)
    if not ok:
        print(f"config: FAIL: {msg}")
        return 1
    pin_problems = check_pins()
    if pin_problems:
        print("pins: WARN: " + "; ".join(pin_problems))
    if args.contamination_scan:
        clean, detail = _contamination_scan()
        print(f"contamination: {'ok' if clean else 'FAIL'}")
        if not clean:
            print(detail)
            return 1
    if args.probe_backend:
        backend_ok, backend_msg = asyncio.run(_probe_backend(args.config))
        print(f"backend: {'ok' if backend_ok else 'FAIL'}: {backend_msg}")
        if not backend_ok:
            return 1
    print("doctor: ok")
    return 0


async def _probe_backend(config_path: str) -> tuple[bool, str]:
    cfg = load_config(config_path, require_runtime_secrets=False)
    try:
        async with HermesMCPClientShim(cfg) as shim:
            tools = await shim.list_tools()
    except Exception as exc:
        return False, redact_text(f"{type(exc).__name__}: {exc}")
    if not tools:
        return False, "backend listed zero tools"
    return True, f"{len(tools)} tools"


def probe_hermes(args: argparse.Namespace) -> int:
    for k, v in probe().items():
        print(f"{k}: {v}")
    return 0


async def _demo_local(config_path: str | Path | None = None) -> int:
    cfg = load_config(config_path or ROOT / "examples" / "local-direct.yaml")
    bridge_address, visible_count, echo_result, error, audit_count = await run_local_roundtrip(cfg)
    print(f"bridge address: {bridge_address}")
    print(f"visible tool count: {visible_count}")
    print(f"echo result: {echo_result}")
    if error:
        print(f"echo error: {error}")
    print(f"audit event count: {audit_count}")
    return 0 if not error and echo_result == "hello" else 1


async def _demo_tool(config_path: str | Path, tool: str, args_json: str) -> int:
    cfg = load_config(config_path)
    try:
        tool_args = json.loads(args_json)
    except json.JSONDecodeError as exc:
        print(f"args-json: FAIL: {exc}")
        return 1
    if not isinstance(tool_args, dict):
        print("args-json: FAIL: expected a JSON object")
        return 1
    bridge_address, visible_count, result, error, audit_count = await run_local_tool_roundtrip(
        cfg, tool, tool_args
    )
    print(f"bridge address: {bridge_address}")
    print(f"visible tool count: {visible_count}")
    print(f"{tool} result: {result}")
    if error:
        print(f"{tool} error: {error}")
    print(f"audit event count: {audit_count}")
    return 0 if not error and result else 1


async def _demo_mailbox(config_path: str | Path, duration_seconds: float) -> int:
    if duration_seconds <= 0:
        print("mailbox demo: FAIL: duration must be positive")
        return 1
    cfg = load_config(config_path)
    if cfg.agent.mode != "mailbox":
        print("mailbox demo: FAIL: config agent.mode must be mailbox")
        return 1
    print("mailbox demo: starting bridge in mailbox mode")
    print("mailbox demo: seed loaded from environment; secret values are not printed")
    try:
        address = await run_bridge_for(cfg, duration_seconds)
    except Exception as exc:
        print(f"mailbox demo: FAIL: {type(exc).__name__}: {redact_text(str(exc))}")
        return 1
    print(f"mailbox demo: bridge address: {address}")
    print(f"mailbox demo: completed {duration_seconds:g}s startup window")
    return 0


async def _demo_payment_dry_run(config_path: str | Path) -> int:
    cfg = load_config(config_path)
    if cfg.payment.mode != "dry_run":
        print("payment dry-run: FAIL: config payment.mode must be dry_run")
        return 1
    if not cfg.payment.priced_tools:
        print("payment dry-run: FAIL: at least one priced tool is required")
        return 1
    audit = AuditWriter(cfg.audit_path)
    before_count = audit.count()
    tool = next(iter(cfg.payment.priced_tools))
    sender = "local-demo-buyer"
    store = PaymentDryRunStore()
    request = store.request(cfg, sender=sender, tool=tool, bridge_address="agent1dryrun")
    audit.write(
        sender=sender,
        protocol="payment",
        msg_type="payment_request",
        decision="quote",
        reason="dry-run quote created",
        payment_reference=request.reference,
        payment_status="requested",
        payment_method=request.accepted_funds[0].payment_method,
        payment_currency=request.accepted_funds[0].currency,
        payment_amount=request.accepted_funds[0].amount,
        payment_mode=cfg.payment.mode,
    )
    commit_cls = __import__(
        "uagents_core.contrib.protocols.payment",
        fromlist=["CommitPayment"],
    ).CommitPayment
    commit = commit_cls(
        funds=request.accepted_funds[0],
        recipient=request.recipient,
        transaction_id=dryrun_transaction_id(),
        reference=request.reference,
        description="dry-run local commitment; no funds moved",
        metadata={"mode": "dry_run"},
    )
    complete = store.commit(sender, commit)
    decision = "complete" if complete.__class__.__name__ == "CompletePayment" else "cancel"
    audit.write(
        sender=sender,
        protocol="payment",
        msg_type="payment_commit",
        decision=decision,
        reason=getattr(complete, "reason", None) or "ok",
        payment_reference=request.reference,
        payment_status=decision,
        payment_method=commit.funds.payment_method,
        payment_currency=commit.funds.currency,
        payment_amount=commit.funds.amount,
        payment_mode=cfg.payment.mode,
        transaction_id_short=getattr(complete, "transaction_id", None),
    )
    print("payment dry-run: request created")
    print(f"payment dry-run: reference: {request.reference}")
    print(
        "payment dry-run: accepted: "
        f"{request.accepted_funds[0].amount} {request.accepted_funds[0].currency} "
        f"via {request.accepted_funds[0].payment_method}"
    )
    print(f"payment dry-run: commit decision: {decision}")
    print(f"payment dry-run: completion: {complete.__class__.__name__}")
    print(f"payment dry-run: audit event count: {audit.count() - before_count}")
    print("payment dry-run: no real funds moved; no wallet secret or FET spend used")
    return 0 if complete.__class__.__name__ == "CompletePayment" else 1


def demo(args: argparse.Namespace) -> int:
    if args.kind == "mailbox":
        cfg_path = args.config or ROOT / "examples" / "agentverse-mailbox-hermes.yaml"
        ok, msg = validate_config_file(cfg_path)
        if not ok:
            print(f"mailbox demo: FAIL: {msg}")
            print(
                "mailbox demo: set UAGENT_SEED only in the operator shell and "
                "see research/HOSTED_DEMO_BLOCKER.md"
            )
            return 1
        return asyncio.run(_demo_mailbox(cfg_path, args.duration_seconds))
    if args.kind in {"payment", "payment-dry-run"}:
        cfg_path = args.config or ROOT / "examples" / "payment-dry-run.yaml"
        return asyncio.run(_demo_payment_dry_run(cfg_path))
    if args.kind == "hermes":
        cfg_path = args.config or ROOT / "examples" / "hermes-stdio.yaml"
        return asyncio.run(_demo_tool(cfg_path, args.tool, args.args_json))
    return asyncio.run(_demo_local(args.config))


def serve(args: argparse.Namespace) -> int:
    from .uagent_app import run_bridge

    cfg = load_config(args.config)
    asyncio.run(run_bridge(cfg))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hermes-fetch-ai")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("doctor")
    d.add_argument("--config", default=str(ROOT / "examples" / "local-direct.yaml"))
    d.add_argument("--contamination-scan", action="store_true")
    d.add_argument("--probe-backend", action="store_true")
    d.set_defaults(func=doctor)
    ph = sub.add_parser("probe-hermes")
    ph.set_defaults(func=probe_hermes)
    s = sub.add_parser("serve")
    s.add_argument("--config", required=True)
    s.set_defaults(func=serve)
    dm = sub.add_parser("demo")
    dm.add_argument("kind", choices=["local", "hermes", "mailbox", "payment", "payment-dry-run"])
    dm.add_argument("--config", default=None)
    dm.add_argument("--tool", default="conversations_list")
    dm.add_argument("--args-json", default='{"limit": 1}')
    dm.add_argument("--duration-seconds", type=float, default=30.0)
    dm.set_defaults(func=demo)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
