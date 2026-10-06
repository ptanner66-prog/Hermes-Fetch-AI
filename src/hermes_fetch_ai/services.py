"""Services this agent sells, and how a request for one is priced, paid, and run.

Each service the owner configures appears to other agents as the tool
``service.<name>`` with one text argument, ``request``. A priced service
answers an unpaid call with the payment terms; the buyer pays on the ledger
and repeats the call with the proof. Paid or free, the request runs once
through the service's runner, and the answer carries the service's
disclaimer.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from collections import OrderedDict
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .arg_validator import validate_args
from .config import BridgeConfig, CommandRunnerConfig, RunnerConfig, ServiceConfig
from .ledger import normalize_tx_hash
from .logging import get_logger
from .money import format_fet
from .programs import ProgramRunner, ServiceResult, base_env
from .quotes import request_digest
from .result_normalizer import error_result, text_result
from .seller import PaymentProof, PaymentRefused, Seller, short_reference, short_tx
from .store import Credit

logger = get_logger("hermes_fetch_ai")

SERVICE_PREFIX = "service."
_DAY_MS = 86_400_000
BUSY = "this service is busy; try again in a few minutes"
CALL_RETRY_HINT = "; your payment is kept, so you can repeat the call with the same reference"
# A paid answer is kept in memory this long, so a buyer who missed it can ask again.
_ANSWER_TTL_SECONDS = 3600.0
_MAX_KEPT_ANSWERS = 64


class ServiceRunner(Protocol):
    async def run(self, request: str) -> ServiceResult: ...


class EchoRunner:
    """Answers with the request; for demos and tests."""

    async def run(self, request: str) -> ServiceResult:
        return ServiceResult(text=request, ok=True)


class CommandRunner(ProgramRunner):
    """Runs the owner's program: the request as JSON on stdin, the answer on stdout.

    The program sees only a short environment allowlist plus the variables
    named in ``pass_env``. A non-zero exit or a timeout is a runner failure.
    """

    def __init__(self, cfg: CommandRunnerConfig, *, show_errors: bool = False) -> None:
        super().__init__(
            timeout_seconds=cfg.timeout_seconds,
            # Read a little past the cap: the answer is cut to max_output_chars anyway.
            read_limit=cfg.max_output_chars * 4 + 4,
            show_errors=show_errors,
        )
        self.cfg = cfg

    def command(self, workdir: str) -> tuple[list[str], dict[str, str]]:
        return list(self.cfg.argv), base_env(workdir, self.cfg.pass_env)

    def payload(self, request: str) -> bytes:
        return json.dumps({"request": request}).encode("utf-8")

    def answer(self, output: bytes, returncode: int | None, overflowed: bool) -> ServiceResult:
        # A program stopped for writing too much still produced an answer.
        if returncode != 0 and not overflowed:
            return ServiceResult(
                "", ok=False, problem=f"the service program failed (exit {returncode})"
            )
        text = output.decode("utf-8", errors="replace")
        if overflowed or len(text) > self.cfg.max_output_chars:
            text = text[: self.cfg.max_output_chars] + "\n[…answer truncated]"
        return ServiceResult(text, ok=True)


def program_problems(cfg: BridgeConfig) -> list[str]:
    """Why a configured service program could not run, one line per problem.

    A program that cannot start would take buyers' payments and fail every
    run, so the bridge refuses to start with any of these.
    """
    problems = []
    for name, svc in cfg.services.items():
        runner = svc.runner
        if not isinstance(runner, CommandRunnerConfig):
            continue
        program = Path(runner.argv[0])
        if not program.is_file():
            problems.append(f"service {name}: program {program} not found")
        elif not os.access(program, os.X_OK):
            problems.append(f"service {name}: program {program} is not executable")
        problems.extend(
            f"service {name}: {arg} not found"
            for arg in runner.argv[1:]
            if Path(arg).is_absolute() and not Path(arg).exists()
        )
    return problems


def build_runner(cfg: RunnerConfig, *, show_errors: bool = False) -> ServiceRunner:
    if cfg.type == "command":
        return CommandRunner(cfg, show_errors=show_errors)
    return EchoRunner()


def service_tool_name(name: str) -> str:
    return SERVICE_PREFIX + name


def service_tool(name: str, svc: ServiceConfig, cfg: BridgeConfig) -> dict[str, Any]:
    """The MCP tool descriptor other agents see for a service."""
    price = svc.price_base
    price_text = (
        f"Price: {format_fet(price)} testnet FET per request (Fetch testnet, paid on the ledger)."
        if price
        else "Free."
    )
    return {
        "name": service_tool_name(name),
        "description": f"{svc.title}. {svc.description} {price_text}",
        "inputSchema": {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": svc.input.max_chars,
                    "description": "What you want, in plain language.",
                }
            },
            "required": ["request"],
            "additionalProperties": False,
        },
        "_meta": {
            "hermes_fetch_ai": {
                "price": format_fet(price),
                "currency": "FET",
                "denom": cfg.payments.denom,
                "chain_id": cfg.payments.chain_id,
                "network": cfg.payments.network,
                "payment_method": "fet_direct",
            }
        },
    }


def credit_audit(credit: Credit) -> dict[str, Any]:
    """Audit fields for a verified payment, in short forms only."""
    return {
        "payment": "verified",
        "credit": short_reference(credit.reference),
        "amount_base": str(credit.amount_base),
        "tx_short": short_tx(credit.tx_hash),
        "payer_short": short_tx(credit.payer),
    }


class ServiceBusy(Exception):
    """Every running and waiting place for a service is taken."""


class RunSlots:
    """Runs of one service: at most ``running`` at once and ``waiting`` more in line."""

    def __init__(self, running: int, waiting: int) -> None:
        self._semaphore = asyncio.Semaphore(running)
        self._limit = running + waiting
        self._inside = 0

    def busy(self) -> bool:
        return self._inside >= self._limit

    @contextlib.asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """Wait for a run; raise ServiceBusy at once if the line is full."""
        if self.busy():
            raise ServiceBusy
        self._inside += 1
        try:
            async with self._semaphore:
                yield
        finally:
            self._inside -= 1


@dataclass(frozen=True)
class _KeptAnswer:
    tx_hash: str
    text: str
    output_bytes: int
    truncated: bool
    expires: float


@dataclass
class ServiceOutcome:
    """A service call's response plus what the audit log should record."""

    text: str
    is_error: bool
    decision: str
    reason: str
    output_bytes: int = 0
    truncated: bool = False
    audit: dict[str, Any] = field(default_factory=dict)


class ServiceDesk:
    """Sells the configured services: listing, pricing, payment, and running."""

    def __init__(
        self,
        cfg: BridgeConfig,
        seller: Seller,
        runners: Mapping[str, ServiceRunner] | None = None,
    ) -> None:
        self.cfg = cfg
        self.seller = seller
        self.runners: dict[str, ServiceRunner] = {
            name: build_runner(svc.runner) for name, svc in cfg.services.items()
        }
        if runners:
            self.runners.update(runners)
        self._tool_names = {service_tool_name(name): name for name in cfg.services}
        self._slots = {
            name: RunSlots(svc.max_running, svc.max_waiting) for name, svc in cfg.services.items()
        }
        # Paid answers by quote reference, oldest first; memory only, never on disk.
        self._answers: OrderedDict[str, _KeptAnswer] = OrderedDict()
        self._clock = time.monotonic

    def has(self, tool_name: str) -> bool:
        return tool_name in self._tool_names

    def tools(self, sender: str) -> list[dict[str, Any]]:
        store = self.seller.store
        if store.paused() or store.is_banned(sender):
            return []
        return [
            service_tool(name, svc, self.cfg)
            for name, svc in self.cfg.services.items()
            if service_tool_name(name) not in self.cfg.policy.denied_tools
        ]

    def _refuse(self, text: str, *, decision: str = "denied", **audit: Any) -> ServiceOutcome:
        capped = error_result(text, self.cfg.policy.max_output_bytes)
        return ServiceOutcome(capped.text, True, decision, text.split(":", 1)[0], audit=audit)

    def _keep(self, reference: str, tx_hash: str, outcome: ServiceOutcome) -> None:
        now = self._clock()
        self._answers[reference] = _KeptAnswer(
            tx_hash,
            outcome.text,
            outcome.output_bytes,
            outcome.truncated,
            now + _ANSWER_TTL_SECONDS,
        )
        while self._answers and (
            len(self._answers) > _MAX_KEPT_ANSWERS
            or next(iter(self._answers.values())).expires <= now
        ):
            self._answers.popitem(last=False)

    def _kept(self, proof: PaymentProof) -> _KeptAnswer | None:
        kept = self._answers.get(proof.reference)
        if kept is None or kept.expires <= self._clock():
            return None
        with contextlib.suppress(ValueError):
            if normalize_tx_hash(proof.tx_hash) == kept.tx_hash:
                return kept
        return None

    def name_of(self, tool_name: str) -> str:
        return self._tool_names[tool_name]

    def busy(self, name: str) -> bool:
        return self._slots[name].busy()

    async def admit(self, name: str, sender: str, args: dict[str, Any]) -> str | None:
        """Why this request may not be served now, or None: owner controls, input, daily limit."""
        svc = self.cfg.services[name]
        store = self.seller.store
        if store.paused():
            return "this agent is not taking requests right now"
        if store.is_banned(sender):
            return "this agent does not accept your requests"
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    validate_args,
                    service_tool(name, svc, self.cfg),
                    args,
                    self.cfg,
                    shell_checks=False,
                    url_checks=svc.input.check_urls,
                ),
                timeout=self.cfg.hermes_mcp.timeout_seconds,
            )
        except TimeoutError:
            return "argument checks timed out"
        except (TypeError, ValueError) as exc:
            return str(exc)
        if store.runs_since(name, int(time.time() * 1000) - _DAY_MS) >= svc.max_runs_per_day:
            return "this service has reached its limit for today; try again tomorrow"
        return None

    async def call(
        self,
        *,
        sender: str,
        tool_name: str,
        args: dict[str, Any],
        proof: PaymentProof | None,
        remember_replay: Callable[[], tuple[bool, str]],
    ) -> ServiceOutcome:
        """Serve one MCP call to ``service.<name>``: quote, verify payment, run."""
        name = self.name_of(tool_name)
        svc = self.cfg.services[name]
        problem = await self.admit(name, sender, args)
        if problem is not None:
            return self._refuse(problem)
        price = svc.price_base
        credit = None
        audit: dict[str, Any] = {}
        if price:
            digest = request_digest(args)
            if proof is None:
                # Never ask for money that cannot be worked off soon.
                if self.busy(name):
                    return self._refuse(BUSY)
                quote, reference = self.seller.quote(
                    kind="call", sender=sender, subject=name, digest=digest, amount_base=price
                )
                text = self.seller.payment_required(quote, reference)
                return ServiceOutcome(
                    text,
                    True,
                    "payment",
                    "payment required",
                    audit={
                        "payment": "required",
                        "credit": short_reference(reference),
                        "amount_base": str(price),
                    },
                )
            try:
                credit = await self.seller.redeem(proof, sender=sender, subject=name, digest=digest)
            except PaymentRefused as exc:
                # The quote check inside redeem proved this is the buyer who paid,
                # and the replay check stops a copied message from collecting it.
                kept = self._kept(proof) if exc.status == "done" else None
                if kept is None:
                    return self._refuse(exc.reason, payment=exc.status)
                ok, why = remember_replay()
                if not ok:
                    return self._refuse(why, payment=exc.status)
                return ServiceOutcome(
                    kept.text,
                    False,
                    "allowed",
                    "answer sent again",
                    output_bytes=kept.output_bytes,
                    truncated=kept.truncated,
                    audit={"payment": "repeat", "credit": short_reference(proof.reference)},
                )
            audit = credit_audit(credit)
        elif self.busy(name):
            return self._refuse(BUSY)

        ok, why = remember_replay()
        if not ok:
            return self._refuse(why, **audit)
        return await self.serve(name, sender, str(args["request"]), credit, audit)

    async def serve(
        self,
        name: str,
        sender: str,
        request: str,
        credit: Credit | None,
        audit: dict[str, Any],
        *,
        retry_hint: str = CALL_RETRY_HINT,
    ) -> ServiceOutcome:
        """Run a request that passed every check, in one of the service's run slots.

        ``retry_hint`` tells a paying buyer how to retry after a failure on the
        seller's side; it differs between MCP calls and chat.
        """
        try:
            async with self._slots[name].slot():
                return await self._run(name, sender, request, credit, audit, retry_hint)
        except ServiceBusy:
            kept_payment = "; your payment is kept, so you can repeat the call shortly"
            return self._refuse(BUSY + (kept_payment if credit else ""), **audit)

    async def _run(
        self,
        name: str,
        sender: str,
        request: str,
        credit: Credit | None,
        audit: dict[str, Any],
        retry_hint: str,
    ) -> ServiceOutcome:
        svc = self.cfg.services[name]
        if credit is not None:
            try:
                credit = self.seller.begin(credit)
            except PaymentRefused as exc:
                return self._refuse(exc.reason, **audit)
        self.seller.store.record_run(subject=name, sender=sender, now_ms=int(time.time() * 1000))
        try:
            result = await self.runners[name].run(request)
        except Exception:  # a runner bug must not lose the payment
            logger.exception("service %s runner failed", name)
            result = ServiceResult("", ok=False, problem="the service failed")
        if credit is not None:
            credit = self.seller.finish(credit, ok=result.ok)
        if not result.ok:
            retry = credit is not None and credit.status == "paid"
            hint = (
                retry_hint
                if retry
                else ("; ask the seller for a refund" if credit is not None else "")
            )
            return self._refuse(result.problem + hint, decision="error", **audit)
        answer = result.text.rstrip()  # programs end their output with a newline
        if svc.disclaimer:
            answer = f"{answer}\n\n— {svc.disclaimer}"
        capped = text_result(answer, self.cfg.policy.max_output_bytes)
        outcome = ServiceOutcome(
            capped.text,
            False,
            "allowed",
            "ok",
            output_bytes=capped.output_bytes,
            truncated=capped.truncated,
            audit=audit,
        )
        if credit is not None:
            self._keep(credit.reference, credit.tx_hash, outcome)
        return outcome

    async def aclose(self) -> None:
        await self.seller.aclose()
