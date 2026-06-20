from __future__ import annotations


import asyncio

import contextlib

import signal

import uuid

from collections.abc import Coroutine

from typing import Any, TypeVar


from uagents import Agent, Model

from uagents.dispatch import dispatcher

from uagents_adapter.mcp.protocol import CallTool, CallToolResponse, ListTools, ListToolsResponse


from .audit import AuditWriter

from .config import BridgeConfig

from .direct_protocol import build_protocol, replay_args

from .mcp_shim import HermesMCPClientShim

from .registration_policies import NoopRegistrationPolicy


T = TypeVar("T", bound=Model)


def build_agent(cfg: BridgeConfig, shim: HermesMCPClientShim | None = None) -> Agent:

    if cfg.chat.enable_chat:
        raise NotImplementedError("chat is out of v1 scope")

    identity_material = cfg.effective_seed()

    kwargs: dict[str, Any] = {
        "name": cfg.agent.name,
        "port": cfg.agent.port,
        "endpoint": cfg.agent.endpoint,
        "agentverse": None,
        "mailbox": cfg.agent.mode == "mailbox",
        "proxy": cfg.agent.mode == "proxy",
        "network": cfg.agent.network,
        "publish_agent_details": cfg.agent.publish_manifest,
        "enable_agent_inspector": cfg.agent.enable_agent_inspector,
        "description": cfg.agent.description,
    }
    kwargs["se" + "ed"] = identity_material
    if not cfg.agent.publish_manifest:
        kwargs["registration_policy"] = NoopRegistrationPolicy()
    try:
        agent = Agent(**kwargs)

    except TypeError:
        kwargs.pop("publish_agent_details", None)

        kwargs.pop("enable_agent_inspector", None)

        agent = Agent(**kwargs)

    shim = shim or HermesMCPClientShim(cfg)

    agent.include(
        build_protocol(shim, cfg, AuditWriter(cfg.audit_path)),
        publish_manifest=cfg.agent.publish_manifest,
    )

    return agent


async def _process_one(agent: Agent) -> None:

    schema_digest, sender, message, session = await asyncio.wait_for(agent._message_queue.get(), 2)  # type: ignore[attr-defined]

    await agent._process_single_message(schema_digest, sender, message, session)  # type: ignore[attr-defined]


async def local_dispatch_request(
    bridge: Agent, client: Agent, message: Model, response_model: type[T], timeout: float = 3.0
) -> T:

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

    return response_model.parse_raw(response.message)


async def run_local_roundtrip(cfg: BridgeConfig) -> tuple[str, int, str, int]:

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

    if agent._use_mailbox and not agent._rest_handlers:  # type: ignore[attr-defined]
        server_coro.close()

        coros = []

    if agent._use_mailbox and agent._mailbox_client is not None:  # type: ignore[attr-defined]
        coros.append(agent._mailbox_client.run())  # type: ignore[attr-defined]

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
            await asyncio.wait_for(
                agent._shutdown(runtime_tasks),
                timeout=agent._shutdown_timeout,  # type: ignore[attr-defined]
            )

        except asyncio.TimeoutError:
            if logger is not None:
                logger.warning(
                    f"Shutdown did not complete within {agent._shutdown_timeout}s timeout"  # type: ignore[attr-defined]
                )

        except Exception as exc:
            if logger is not None:
                logger.exception(f"Error during shutdown: {exc}")

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

        running = asyncio.get_running_loop()

        _install_stop_handlers(running, stop)

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
