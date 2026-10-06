from __future__ import annotations

import asyncio
import contextlib
import signal
import uuid
from collections.abc import Coroutine
from typing import Any, TypeVar, cast

import uagents.agent as uagents_agent
from uagents import Agent, Model
from uagents.dispatch import dispatcher
from uagents_adapter.mcp.protocol import CallTool, CallToolResponse, ListTools, ListToolsResponse

from .audit import AuditWriter
from .config import BridgeConfig
from .direct_protocol import build_protocol, replay_args
from .mcp_shim import HermesMCPClientShim
from .registration_policies import NoopRegistrationPolicy

T = TypeVar("T", bound=Model)


class PrivateAgent(Agent):
    """A uAgent that never contacts the Almanac, for ``publish_manifest: false``.

    uAgents looks up the Almanac contract on the Fetch ledger whenever an agent
    is created, and reports the agent as active at startup and inactive at
    shutdown through the Almanac API, even when registration is disabled. Only
    ledger registration needs the contract, and a private bridge never registers
    or announces its address, so both are skipped.
    """

    def __init__(self, **kwargs: Any) -> None:
        lookup = uagents_agent.get_almanac_contract
        uagents_agent.get_almanac_contract = _no_almanac_contract
        try:
            super().__init__(**kwargs)
        finally:
            uagents_agent.get_almanac_contract = lookup

    async def _update_agent_status(self, active: bool) -> None:
        return None


def _no_almanac_contract(network: str = "testnet") -> None:
    return None


def build_agent(cfg: BridgeConfig, shim: HermesMCPClientShim | None = None) -> Agent:
    if cfg.chat.enable_chat:
        raise NotImplementedError("chat is out of v1 scope")

    kwargs: dict[str, Any] = {
        "name": cfg.agent.name,
        "port": cfg.agent.port,
        "seed": cfg.effective_seed(),
        "endpoint": cfg.agent.endpoint,
        "agentverse": None,
        "mailbox": cfg.agent.mode == "mailbox",
        "proxy": cfg.agent.mode == "proxy",
        "network": cfg.agent.network,
        "publish_agent_details": cfg.agent.publish_manifest,
        "enable_agent_inspector": cfg.agent.enable_agent_inspector,
        "description": cfg.agent.description,
    }
    if cfg.agent.publish_manifest:
        # Leave registration to uAgents' default ledger-backed policy, so a
        # funded wallet can pay for Almanac registration.
        agent = Agent(**kwargs)
    else:
        agent = PrivateAgent(
            **kwargs,
            registration_policy=NoopRegistrationPolicy(),
            mark_inactive_on_shutdown=False,
        )

    agent.include(
        build_protocol(shim or HermesMCPClientShim(cfg), cfg, AuditWriter(cfg.audit_path)),
        publish_manifest=cfg.agent.publish_manifest,
    )
    return agent


async def _process_one(agent: Agent) -> None:
    # uAgents has no public API to process one queued message, which the
    # in-process demo needs to stay deterministic.
    schema_digest, sender, message, session = await asyncio.wait_for(agent._message_queue.get(), 2)
    await agent._process_single_message(schema_digest, sender, message, session)


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
    """Run the local demo: a client uAgent lists tools and calls echo on the bridge."""
    audit_path = cfg.audit_path
    audit_path.unlink(missing_ok=True)

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
        AuditWriter(audit_path).count(),
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


def _agent_runtime_coroutines(agent: Agent) -> list[Coroutine[Any, Any, Any]]:
    """Return the uAgents runtime coroutines normally created by Agent.run_async()."""
    server_coro = agent.start_server()
    coros: list[Coroutine[Any, Any, Any]] = [server_coro]
    if agent._use_mailbox and not agent._rest_handlers:
        server_coro.close()
        coros = []
    if agent._use_mailbox and agent._mailbox_client is not None:
        coros.append(agent._mailbox_client.run())
    return coros


async def _run_agent_until_stop(agent: Agent, stop: asyncio.Event) -> None:
    """Run an Agent until stop is set, then perform uAgents graceful shutdown.

    Agent.run_async() owns process lifetime and cancels every task on the loop
    during teardown. The bridge has one extra lifetime task (the signal stop
    waiter), so using run_async() directly can cancel the bridge supervisor and
    close the loop while uAgents shutdown coroutines are still alive. This small
    supervisor mirrors uAgents' startup path but keeps shutdown ownership in the
    bridge, producing deterministic rc=0 exits on Windows and Unix.
    """
    agent.setup()
    runtime_tasks = [asyncio.create_task(coro) for coro in _agent_runtime_coroutines(agent)]
    stop_task = asyncio.create_task(stop.wait())
    try:
        done, _ = await asyncio.wait(
            {stop_task, *runtime_tasks}, return_when=asyncio.FIRST_COMPLETED
        )
        if stop_task not in done:
            for task in done:
                task.result()
    except (asyncio.CancelledError, KeyboardInterrupt):
        stop.set()
    finally:
        stop_task.cancel()
        with contextlib.suppress(BaseException):
            await stop_task

        logger = getattr(agent, "_logger", None)
        if logger is not None:
            logger.info("Shutting down agent...")
        try:
            await asyncio.wait_for(agent._shutdown(runtime_tasks), timeout=agent._shutdown_timeout)
        except TimeoutError:
            if logger is not None:
                logger.warning(
                    f"Shutdown did not complete within {agent._shutdown_timeout}s timeout"
                )
        except Exception:
            if logger is not None:
                logger.exception("Error during shutdown")
            else:
                raise

        remaining = [
            task
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task() and not task.done()
        ]
        for task in remaining:
            task.cancel()
        if remaining:
            await asyncio.gather(*remaining, return_exceptions=True)
        if logger is not None:
            logger.info("Shutting down agent...complete.")


def run_bridge(cfg: BridgeConfig) -> None:
    """Run the bridge agent until it exits or SIGINT/SIGTERM/SIGBREAK arrives."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    stop = asyncio.Event()

    async def _main() -> None:
        _install_stop_handlers(asyncio.get_running_loop(), stop)
        async with HermesMCPClientShim(cfg) as shim:
            agent = build_agent(cfg, shim)
            await _run_agent_until_stop(agent, stop)

    try:
        with contextlib.suppress(KeyboardInterrupt, asyncio.CancelledError):
            loop.run_until_complete(_main())
    finally:
        with contextlib.suppress(Exception):
            loop.run_until_complete(loop.shutdown_asyncgens())
        with contextlib.suppress(Exception):
            loop.stop()
            loop.close()
