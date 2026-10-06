from __future__ import annotations

import asyncio
import contextlib
import signal
import uuid
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any, TypeVar, cast

import uagents.agent as uagents_agent
from uagents import Agent, Model
from uagents.dispatch import dispatcher
from uagents.registration import AlmanacApiRegistrationPolicy
from uagents_adapter.mcp.protocol import CallTool, CallToolResponse, ListTools, ListToolsResponse

from .audit import AuditWriter
from .buyer import Buyer, SendInSession
from .chat_protocol import build_chat_protocols
from .config import BridgeConfig
from .control import ControlServer, control_path
from .direct_protocol import build_protocol, replay_args
from .ledger import LcdLedgerReader, LedgerReader
from .mcp_shim import HermesMCPClientShim
from .quotes import quote_key
from .registration_policies import NoopRegistrationPolicy
from .seller import Seller
from .sender import CosmpySender, PaymentSender
from .services import ServiceDesk, ServiceRunner
from .store import Store
from .wallet import BUYING_WALLET_INDEX, agent_address, wallet_address, wallet_for

T = TypeVar("T", bound=Model)


class ApiRegisteredAgent(Agent):
    """A uAgent created without looking up the Almanac contract on the ledger.

    uAgents looks the contract up whenever an agent is created, but only ledger
    registration, which can spend from the agent's wallet, needs it. A bridge
    registers through the Almanac API instead, unless the owner turns on
    ``agent.ledger_registration``.
    """

    def __init__(self, **kwargs: Any) -> None:
        lookup = uagents_agent.get_almanac_contract
        uagents_agent.get_almanac_contract = _no_almanac_contract
        try:
            super().__init__(**kwargs)
        finally:
            uagents_agent.get_almanac_contract = lookup


class PrivateAgent(ApiRegisteredAgent):
    """A uAgent that never contacts the Almanac, for ``publish_manifest: false``.

    Besides the contract lookup, uAgents reports every agent as active at
    startup and inactive at shutdown through the Almanac API, even when
    registration is disabled. A private bridge never registers or announces its
    address, so that is skipped too.
    """

    async def _update_agent_status(self, active: bool) -> None:
        return None


def _no_almanac_contract(network: str = "testnet") -> None:
    return None


def payment_store_path(cfg: BridgeConfig, seed: str) -> Path:
    """Where this agent's payment records live: one directory per agent address."""
    return cfg.payments.state_path / agent_address(seed) / "payments.sqlite3"


def _lcd(cfg: BridgeConfig) -> Callable[[], LedgerReader]:
    payments = cfg.payments

    def lcd() -> LedgerReader:
        return LcdLedgerReader(payments.ledger_url, payments.ledger_timeout_seconds)

    return lcd


def build_service_desk(
    cfg: BridgeConfig,
    seed: str,
    *,
    ledger_factory: Callable[[], LedgerReader] | None = None,
    runners: dict[str, ServiceRunner] | None = None,
    store: Store | None = None,
) -> ServiceDesk:
    """The seller side of a bridge with ``payments.enabled``: services, payments, records."""
    payments = cfg.payments
    seller = Seller(
        payments=payments,
        store=store or Store.open(payment_store_path(cfg, seed)),
        key=quote_key(seed),
        payout=payments.payout_address or wallet_address(seed),
        ledger_factory=ledger_factory or _lcd(cfg),
    )
    return ServiceDesk(cfg, seller, runners)


def build_buyer(
    cfg: BridgeConfig,
    seed: str,
    store: Store,
    *,
    sender: PaymentSender | None = None,
    ledger_factory: Callable[[], LedgerReader] | None = None,
) -> Buyer:
    """The buying side of a bridge with ``buying.enabled``; it pays from the buying wallet."""
    return Buyer(
        cfg,
        store,
        AuditWriter(cfg.audit_path),
        sender=sender or CosmpySender(wallet_for(seed, BUYING_WALLET_INDEX), cfg.payments),
        ledger_factory=ledger_factory or _lcd(cfg),
    )


def session_sender(agent: Agent) -> SendInSession:
    """Send a message from ``agent`` in a given chat session, outside any handler.

    uAgents builds the same kind of context for its interval tasks; the
    session it carries is the one the other agent replies in.
    """

    async def send(to: str, message: Model, session: str) -> None:
        ctx = agent._build_context()
        ctx._session = uuid.UUID(session)
        await ctx.send(to, message)

    return send


def build_agent(
    cfg: BridgeConfig,
    shim: HermesMCPClientShim | None = None,
    *,
    seed: str | None = None,
    desk: ServiceDesk | None = None,
    buyer: Buyer | None = None,
) -> Agent:
    kwargs: dict[str, Any] = {
        "name": cfg.agent.name,
        "port": cfg.agent.port,
        "seed": seed or cfg.effective_seed(),
        "endpoint": cfg.agent.endpoint,
        "agentverse": None,
        "mailbox": cfg.agent.mode == "mailbox",
        "proxy": cfg.agent.mode == "proxy",
        "network": cfg.agent.network,
        "publish_agent_details": cfg.agent.publish_manifest,
        "enable_agent_inspector": cfg.agent.enable_agent_inspector,
        "description": cfg.agent.description,
        # uAgents handles one message at a time by default. A paid service can
        # run for minutes, so a seller handles each message in its own task;
        # each service's run slots bound the work.
        "handle_messages_concurrently": cfg.payments.enabled or buyer is not None,
    }
    if cfg.agent.publish_manifest and cfg.agent.ledger_registration:
        # uAgents' default policy: the Almanac API, then the Almanac contract,
        # which a funded wallet pays for.
        agent: Agent = Agent(**kwargs)
    elif cfg.agent.publish_manifest:
        agent = ApiRegisteredAgent(**kwargs, registration_policy=AlmanacApiRegistrationPolicy())
    else:
        agent = PrivateAgent(
            **kwargs,
            registration_policy=NoopRegistrationPolicy(),
            mark_inactive_on_shutdown=False,
        )

    audit = AuditWriter(cfg.audit_path)
    agent.include(
        build_protocol(shim or HermesMCPClientShim(cfg), cfg, audit, desk),
        publish_manifest=cfg.agent.publish_manifest,
    )
    if (cfg.chat.enable_chat and desk is not None) or buyer is not None:
        for protocol in build_chat_protocols(cfg, desk, audit, buyer):
            agent.include(protocol, publish_manifest=cfg.agent.publish_manifest)
    if buyer is not None:
        buyer.send = session_sender(agent)
    return agent


async def _process_one(agent: Agent) -> None:
    # uAgents has no public API to process one queued message, which the
    # in-process demo needs to stay deterministic.
    schema_digest, sender, message, session = await asyncio.wait_for(agent._message_queue.get(), 2)
    await agent._process_single_message(schema_digest, sender, message, session)
    # An agent that handles messages concurrently runs the handler as a task.
    if agent._message_tasks:
        await asyncio.gather(*list(agent._message_tasks))


async def local_dispatch_request(
    bridge: Agent, client: Agent, message: Model, response_model: type[T], timeout: float = 3.0
) -> T:
    """Send ``message`` from ``client`` to ``bridge`` through uAgents' in-process dispatcher."""
    session = uuid.uuid4()
    await dispatcher.register_pending_response(client.address, bridge.address, session)
    await dispatcher.dispatch_msg(
        sender=client.address,
        destination=bridge.address,
        schema_digest=Model.build_schema_digest(message),
        message=message.model_dump_json(),
        session=session,
    )
    await _process_one(bridge)
    response = await dispatcher.wait_for_response(client.address, bridge.address, session, timeout)
    if response is None:
        raise TimeoutError("local dispatcher response timed out")
    return cast(T, response_model.parse_raw(response.message))


async def run_local_roundtrip(cfg: BridgeConfig) -> tuple[str, int, str, int]:
    """Run the local demo: a client uAgent lists tools and calls echo on the bridge.

    Returns the bridge address, the number of tools the client sees, the echo
    result, and the number of records in the audit log at ``cfg.audit_path``.
    """
    async with HermesMCPClientShim(cfg) as shim:
        bridge = build_agent(cfg, shim)
        client_cfg = cfg.model_copy(deep=True)
        client_cfg.agent.name = cfg.agent.name + "_client"
        client = build_agent(client_cfg, shim)
        try:
            list_resp = await local_dispatch_request(bridge, client, ListTools(), ListToolsResponse)
            call_resp = await local_dispatch_request(
                bridge,
                client,
                CallTool(tool="echo", args=replay_args({"text": "hello"})),
                CallToolResponse,
            )
        finally:
            dispatcher.unregister(bridge.address, bridge)
            dispatcher.unregister(client.address, client)

    return (
        bridge.address,
        len(list_resp.tools or []),
        str(call_resp.result),
        AuditWriter(cfg.audit_path).count(),
    )


def _install_stop_handlers(loop: asyncio.AbstractEventLoop, stop: asyncio.Event) -> None:
    """Install cross-platform process stop handlers.

    Unix event loops support add_signal_handler(). Windows' default proactor loop
    does not, so fall back to signal.signal(). The fallback is needed for real
    Windows operators and the HTTP smoke test's CTRL_BREAK_EVENT path.
    """

    def request_stop(*_: object) -> None:
        if not loop.is_closed():
            loop.call_soon_threadsafe(stop.set)

    signals = [signal.SIGINT, signal.SIGTERM]
    if hasattr(signal, "SIGBREAK"):
        signals.append(signal.SIGBREAK)

    for sig in signals:
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError, ValueError):
            with contextlib.suppress(OSError, RuntimeError, ValueError):
                signal.signal(sig, request_stop)


class ServeError(RuntimeError):
    """The bridge's uAgents server stopped on its own."""


async def _supervised(coro: Coroutine[Any, Any, Any], what: str) -> None:
    try:
        await coro
    except SystemExit as exc:
        # uvicorn calls sys.exit() when it cannot start, for example when the
        # port is taken. Inside a task that would tear through the event loop.
        raise ServeError(
            f"{what} stopped during startup (exit status {exc.code}); "
            "is agent.port already in use? See the error logged above."
        ) from None


def _agent_runtime_coroutines(agent: Agent) -> list[Coroutine[Any, Any, Any]]:
    """Return the uAgents runtime coroutines normally created by Agent.run_async()."""
    server_coro = agent.start_server()
    if agent._use_mailbox and not agent._rest_handlers:
        server_coro.close()
        coros = []
    else:
        coros = [_supervised(server_coro, "the bridge's HTTP server")]
    if agent._use_mailbox and agent._mailbox_client is not None:
        coros.append(_supervised(agent._mailbox_client.run(), "the Agentverse mailbox client"))
    return coros


async def _run_agent_until_stop(agent: Agent, stop: asyncio.Event) -> None:
    """Run an Agent until stop is set or its server fails, then shut it down.

    Agent.run_async() owns process lifetime and cancels every task on the loop
    during teardown, which would also cancel the bridge's own tasks, such as
    the Hermes backend's. This supervisor mirrors uAgents' startup path but
    cancels only the agent's tasks, producing deterministic rc=0 exits on
    Windows and Unix. A server failure is raised after the shutdown.
    """
    agent.setup()
    runtime_tasks = [asyncio.create_task(coro) for coro in _agent_runtime_coroutines(agent)]
    stop_task = asyncio.create_task(stop.wait())
    done: set[asyncio.Task[Any]] = set()
    try:
        done, _ = await asyncio.wait(
            {stop_task, *runtime_tasks}, return_when=asyncio.FIRST_COMPLETED
        )
    finally:
        stop_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await stop_task
        agent._logger.info("Shutting down agent...")
        try:
            await asyncio.wait_for(agent._shutdown(runtime_tasks), timeout=agent._shutdown_timeout)
        except TimeoutError:
            agent._logger.warning(
                f"Shutdown did not complete within {agent._shutdown_timeout}s timeout"
            )
        except Exception:
            agent._logger.exception("Error during shutdown")
        agent._logger.info("Shutting down agent...complete.")
    for task in done - {stop_task}:
        task.result()


def _cancel_leftover_tasks(loop: asyncio.AbstractEventLoop) -> None:
    """Cancel tasks uAgents left running, as asyncio.run() does on exit."""
    leftover = [task for task in asyncio.all_tasks(loop) if not task.done()]
    for task in leftover:
        task.cancel()
    if leftover:
        loop.run_until_complete(asyncio.gather(*leftover, return_exceptions=True))


def run_bridge(cfg: BridgeConfig) -> None:
    """Run the bridge agent until SIGINT/SIGTERM/SIGBREAK arrives.

    Raises HermesBackendError if the Hermes backend cannot start and
    ServeError if the agent's server stops on its own.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    stop = asyncio.Event()

    async def _main() -> None:
        _install_stop_handlers(asyncio.get_running_loop(), stop)
        seed = cfg.effective_seed()
        async with HermesMCPClientShim(cfg) as shim:
            store = (
                Store.open(payment_store_path(cfg, seed))
                if cfg.payments.enabled or cfg.buying.enabled
                else None
            )
            desk = buyer = control = None
            try:
                if cfg.payments.enabled:
                    assert store is not None
                    desk = build_service_desk(cfg, seed, store=store)
                if cfg.buying.enabled:
                    assert store is not None
                    buyer = build_buyer(cfg, seed, store)
                agent = build_agent(cfg, shim, seed=seed, desk=desk, buyer=buyer)
                if buyer is not None:
                    control = ControlServer(buyer, control_path(cfg), agent_address=agent.address)
                    await control.start()
                await _run_agent_until_stop(agent, stop)
            finally:
                if control is not None:
                    await control.stop()
                if buyer is not None:
                    await buyer.aclose()
                if desk is not None:
                    await desk.aclose()
                if store is not None:
                    store.close()

    try:
        with contextlib.suppress(KeyboardInterrupt, asyncio.CancelledError):
            loop.run_until_complete(_main())
    finally:
        with contextlib.suppress(Exception):
            _cancel_leftover_tasks(loop)
            loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
