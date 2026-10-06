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
import signal
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .arg_validator import validate_args
from .config import BridgeConfig, CommandRunnerConfig, RunnerConfig, ServiceConfig
from .logging import get_logger
from .money import format_fet
from .quotes import request_digest
from .result_normalizer import error_result, text_result
from .seller import PaymentProof, PaymentRefused, Seller, short_reference, short_tx

logger = get_logger("hermes_fetch_ai")

SERVICE_PREFIX = "service."
_DAY_MS = 86_400_000
# How long a killed service program gets to finish going away.
_STOP_SECONDS = 5.0
# Environment a service program always gets; anything else must be listed in pass_env.
_BASE_ENV = ("PATH", "LANG", "LANGUAGE", "TZ", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT")


@dataclass(frozen=True)
class ServiceResult:
    text: str
    # False when the runner itself failed; the buyer keeps the payment and may retry.
    ok: bool
    problem: str = ""


class ServiceRunner(Protocol):
    async def run(self, request: str) -> ServiceResult: ...


class EchoRunner:
    """Answers with the request; for demos and tests."""

    async def run(self, request: str) -> ServiceResult:
        return ServiceResult(text=request, ok=True)


def _runner_env(pass_env: list[str], workdir: str) -> dict[str, str]:
    env = {name: os.environ[name] for name in _BASE_ENV if name in os.environ}
    env.update({name: value for name, value in os.environ.items() if name.startswith("LC_")})
    env.update({name: os.environ[name] for name in pass_env if name in os.environ})
    env["HOME"] = workdir
    env["TMPDIR"] = workdir
    return env


class CommandRunner:
    """Runs the owner's program: the request as JSON on stdin, the answer on stdout.

    No shell is involved, the program starts in an empty temporary directory
    with a short environment allowlist, stderr is discarded, and both time and
    output size are capped. A non-zero exit or a timeout is a runner failure.
    """

    def __init__(self, cfg: CommandRunnerConfig, *, show_errors: bool = False) -> None:
        self.cfg = cfg
        # Only for the owner's own test runs: buyers never see the program's stderr.
        self.show_errors = show_errors

    async def run(self, request: str) -> ServiceResult:
        with tempfile.TemporaryDirectory(prefix="hermes-fetch-ai-service-") as workdir:
            try:
                process = await asyncio.create_subprocess_exec(
                    *self.cfg.argv,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=None if self.show_errors else asyncio.subprocess.DEVNULL,
                    cwd=workdir,
                    env=_runner_env(self.cfg.pass_env, workdir),
                    start_new_session=os.name != "nt",
                )
            except OSError as exc:
                logger.warning("service program %s could not start (%s)", self.cfg.argv[0], exc)
                return ServiceResult("", ok=False, problem="the service program could not start")
            payload = json.dumps({"request": request}).encode("utf-8")
            try:
                output, overflowed = await asyncio.wait_for(
                    self._exchange(process, payload), self.cfg.timeout_seconds
                )
            except TimeoutError:
                await self._stop(process)
                return ServiceResult("", ok=False, problem="the service took too long")
            # A program stopped for writing too much still produced an answer.
            if process.returncode != 0 and not overflowed:
                return ServiceResult(
                    "", ok=False, problem=f"the service program failed (exit {process.returncode})"
                )
            text = output.decode("utf-8", errors="replace")
            if overflowed or len(text) > self.cfg.max_output_chars:
                text = text[: self.cfg.max_output_chars] + "\n[…answer truncated]"
            return ServiceResult(text, ok=True)

    async def _exchange(
        self, process: asyncio.subprocess.Process, payload: bytes
    ) -> tuple[bytes, bool]:
        """Send the request and read the answer; True if the program wrote too much."""
        assert process.stdin is not None and process.stdout is not None
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            process.stdin.write(payload)
            await process.stdin.drain()
        process.stdin.close()
        # Read a little past the cap, then stop reading so a runaway program
        # cannot fill memory.
        limit = self.cfg.max_output_chars * 4 + 4
        chunks: list[bytes] = []
        size = 0
        while size < limit:
            chunk = await process.stdout.read(min(65536, limit - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        overflowed = size >= limit
        if overflowed:
            await self._stop(process)
        else:
            await process.wait()
        return b"".join(chunks), overflowed

    async def _stop(self, process: asyncio.subprocess.Process) -> None:
        """Kill the program (and anything it started) and wait for it to go.

        asyncio's ``wait()`` also waits for the output pipe to close, and a pipe
        we stopped reading never does, so the leftover output is read and
        dropped. A process that escaped the kill and still holds the pipe open
        is given up on after a few seconds rather than hanging the bridge.
        """
        self._kill(process)
        stdout = process.stdout
        assert stdout is not None

        async def drain() -> None:
            while await stdout.read(65536):
                pass
            await process.wait()

        try:
            await asyncio.wait_for(drain(), _STOP_SECONDS)
        except TimeoutError:
            logger.warning(
                "service program %s left a process holding its output open", self.cfg.argv[0]
            )

    @staticmethod
    def _kill(process: asyncio.subprocess.Process) -> None:
        with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
            if os.name != "nt":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()


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

    async def call(
        self,
        *,
        sender: str,
        tool_name: str,
        args: dict[str, Any],
        proof: PaymentProof | None,
        remember_replay: Callable[[], tuple[bool, str]],
    ) -> ServiceOutcome:
        name = self._tool_names[tool_name]
        svc = self.cfg.services[name]
        store = self.seller.store
        if store.paused():
            return self._refuse("this agent is not taking requests right now")
        if store.is_banned(sender):
            return self._refuse("this agent does not accept your requests")
        descriptor = service_tool(name, svc, self.cfg)
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    validate_args,
                    descriptor,
                    args,
                    self.cfg,
                    shell_checks=False,
                    url_checks=svc.input.check_urls,
                ),
                timeout=self.cfg.hermes_mcp.timeout_seconds,
            )
        except TimeoutError:
            return self._refuse("argument checks timed out")
        except (TypeError, ValueError) as exc:
            return self._refuse(str(exc))
        now_ms = int(time.time() * 1000)
        if store.runs_since(name, now_ms - _DAY_MS) >= svc.max_runs_per_day:
            return self._refuse("this service has reached its limit for today; try again tomorrow")

        price = svc.price_base
        credit = None
        audit: dict[str, Any] = {}
        if price:
            digest = request_digest(args)
            if proof is None:
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
                return self._refuse(exc.reason, payment=exc.status)
            audit = {
                "payment": "verified",
                "credit": short_reference(credit.reference),
                "amount_base": str(credit.amount_base),
                "tx_short": short_tx(credit.tx_hash),
                "payer_short": short_tx(credit.payer),
            }

        ok, why = remember_replay()
        if not ok:
            return self._refuse(why, **audit)
        if credit is not None:
            try:
                credit = self.seller.begin(credit)
            except PaymentRefused as exc:
                return self._refuse(exc.reason, **audit)
        store.record_run(subject=name, sender=sender, now_ms=now_ms)
        try:
            result = await self.runners[name].run(str(args["request"]))
        except Exception:  # a runner bug must not lose the payment
            logger.exception("service %s runner failed", name)
            result = ServiceResult("", ok=False, problem="the service failed")
        if credit is not None:
            credit = self.seller.finish(credit, ok=result.ok)
        if not result.ok:
            retry = credit is not None and credit.status == "paid"
            hint = (
                "; your payment is kept, so you can repeat the call with the same reference"
                if retry
                else ("; ask the seller for a refund" if credit is not None else "")
            )
            return self._refuse(result.problem + hint, decision="error", **audit)
        answer = result.text.rstrip()  # programs end their output with a newline
        if svc.disclaimer:
            answer = f"{answer}\n\n— {svc.disclaimer}"
        capped = text_result(answer, self.cfg.policy.max_output_bytes)
        return ServiceOutcome(
            capped.text,
            False,
            "allowed",
            "ok",
            output_bytes=capped.output_bytes,
            truncated=capped.truncated,
            audit=audit,
        )

    async def aclose(self) -> None:
        await self.seller.aclose()
