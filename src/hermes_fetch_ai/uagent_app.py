from __future__ import annotations

import asyncio
import multiprocessing
import sys
import time
import uuid
from contextlib import contextmanager
from multiprocessing.connection import Connection
from typing import Any, TypeVar

from uagents import Agent, Model
from uagents.dispatch import dispatcher
from uagents_adapter.mcp.protocol import CallTool, CallToolResponse, ListTools, ListToolsResponse

from .audit import AuditWriter
from .config import BridgeConfig
from .direct_protocol import build_protocol
from .mcp_shim import HermesMCPClientShim
from .payments import PaymentDryRunStore
from .registration_policies import NoopRegistrationPolicy

T = TypeVar("T", bound=Model)


def _is_cosmpy_protos_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower().rstrip("/")
    return normalized.endswith("/cosmpy/protos")


@contextmanager
def _without_cosmpy_protos_on_sys_path():
    """Prevent Windows spawn children from resolving google.protobuf via cosmpy stubs.

    Importing uAgents/cosmpy can append ``cosmpy/protos`` to ``sys.path``.
    ``multiprocessing`` spawn copies the parent's path into the child before it
    imports this module. If that copied path starts with cosmpy's vendored
    ``google`` package, cosmpy's own ``from google.protobuf import descriptor``
    resolves to the vendored stub instead of the real protobuf package and the
    child process exits during import. Keep the parent unchanged after the child
    is spawned, but send the child a sanitized import path.
    """

    original = list(sys.path)
    sys.path[:] = [p for p in sys.path if not _is_cosmpy_protos_path(p)]
    try:
        yield
    finally:
        sys.path[:] = original


def build_agent(cfg: BridgeConfig, shim: HermesMCPClientShim | None = None) -> Agent:
    if cfg.chat.enable_chat:
        raise NotImplementedError("chat is out of v1 scope")

    seed = cfg.effective_seed()
    kwargs: dict[str, Any] = {
        "name": cfg.agent.name,
        "seed": seed,
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
    if not cfg.agent.publish_manifest:
        kwargs["registration_policy"] = NoopRegistrationPolicy()

    try:
        agent = Agent(**kwargs)
    except TypeError:
        kwargs.pop("publish_agent_details", None)
        kwargs.pop("enable_agent_inspector", None)
        agent = Agent(**kwargs)

    shim = shim or HermesMCPClientShim(cfg)
    audit = AuditWriter(cfg.audit_path)
    agent.include(build_protocol(shim, cfg, audit), publish_manifest=cfg.agent.publish_manifest)

    if cfg.payment.mode != "disabled":
        if cfg.payment.mode != "dry_run":
            raise ValueError(
                "payment modes beyond dry_run are operator-owned and not started by this proof"
            )
        from .payment_protocol import build_payment_protocol

        agent.include(
            build_payment_protocol(cfg, audit, PaymentDryRunStore()),
            publish_manifest=cfg.agent.publish_manifest,
        )

    return agent


async def _process_one(agent: Agent) -> None:
    schema_digest, sender, message, session = await asyncio.wait_for(
        agent._message_queue.get(), 2  # type: ignore[attr-defined]
    )
    await agent._process_single_message(  # type: ignore[attr-defined]
        schema_digest, sender, message, session
    )


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


async def run_local_tool_roundtrip(
    cfg: BridgeConfig, tool: str, args: dict[str, Any]
) -> tuple[str, int, str, str | None, int]:
    audit = AuditWriter(cfg.audit_path)
    before_count = audit.count()
    async with HermesMCPClientShim(cfg) as shim:
        bridge = build_agent(cfg, shim)
        client_cfg = cfg.model_copy(deep=True)
        client_cfg.agent.name = cfg.agent.name + "_client"
        client = build_agent(client_cfg, shim)
        try:
            list_resp = await local_dispatch_request(bridge, client, ListTools(), ListToolsResponse)
            call_resp = await local_dispatch_request(
                bridge, client, CallTool(tool=tool, args=args), CallToolResponse
            )
        finally:
            dispatcher.unregister(bridge.address, bridge)
            dispatcher.unregister(client.address, client)
    return (
        bridge.address,
        len(list_resp.tools or []),
        "" if call_resp.result is None else str(call_resp.result),
        None if call_resp.error is None else str(call_resp.error),
        audit.count() - before_count,
    )


async def run_local_roundtrip(cfg: BridgeConfig) -> tuple[str, int, str, str | None, int]:
    return await run_local_tool_roundtrip(cfg, "echo", {"text": "hello"})


def _notify_startup(conn: Connection | None, payload: dict[str, str]) -> None:
    if conn is None:
        return
    try:
        conn.send(payload)
    except (BrokenPipeError, EOFError, OSError):
        pass


async def run_bridge(cfg: BridgeConfig, ready_conn: Connection | None = None) -> None:
    conn = ready_conn
    try:
        async with HermesMCPClientShim(cfg) as shim:
            if shim.startup_error is not None:
                raise RuntimeError(f"MCP backend startup failed: {shim.startup_error}")
            agent = build_agent(cfg, shim)
            _notify_startup(conn, {"status": "ready", "address": agent.address})
            conn = None
            agent.run()
    except BaseException as exc:
        _notify_startup(
            conn,
            {"status": "error", "error": f"{exc.__class__.__name__}: {exc}"},
        )
        raise
    finally:
        if conn is not None:
            conn.close()


def _run_bridge_child(cfg: BridgeConfig, ready_conn: Connection | None = None) -> None:
    asyncio.run(run_bridge(cfg, ready_conn=ready_conn))


async def run_bridge_for(cfg: BridgeConfig, seconds: float) -> str:
    """Start the bridge briefly and then shut it down.

    This is used by the hosted mailbox proof path so an operator can verify
    Agentverse/mailbox startup without leaving a long-running process behind.
    The returned address is safe to print; the seed remains only in the
    uAgents runtime/config environment.
    """

    async with HermesMCPClientShim(cfg) as shim:
        if shim.startup_error is not None:
            raise RuntimeError(f"MCP backend startup failed: {shim.startup_error}")
        agent = build_agent(cfg, shim)
        address = agent.address

    parent_conn, child_conn = multiprocessing.Pipe(duplex=False)
    with _without_cosmpy_protos_on_sys_path():
        proc = multiprocessing.Process(
            target=_run_bridge_child, args=(cfg, child_conn), daemon=True
        )
        started = time.monotonic()
        proc.start()
    child_conn.close()

    try:
        readiness_timeout = max(seconds, 5.0)
        try:
            has_message = parent_conn.poll(readiness_timeout)
        except (BrokenPipeError, EOFError, OSError):
            has_message = False
        if not has_message:
            if proc.exitcode is not None:
                raise RuntimeError(
                    "mailbox child process exited before reporting startup readiness "
                    f"with exit code {proc.exitcode}"
                )
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=5)
            raise RuntimeError(
                "mailbox child process did not report startup readiness "
                f"within {readiness_timeout:g}s"
            )
        message = parent_conn.recv()
    finally:
        parent_conn.close()

    status = message.get("status") if isinstance(message, dict) else None
    if status != "ready":
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=5)
        detail = message.get("error", "unknown startup error") if isinstance(message, dict) else message
        raise RuntimeError(f"mailbox child startup failed: {detail}")

    child_address = str(message.get("address") or address)
    remaining = seconds - (time.monotonic() - started)
    if remaining > 0:
        await asyncio.sleep(remaining)
    if proc.exitcode is not None:
        raise RuntimeError(
            f"mailbox child process exited during startup window with exit code {proc.exitcode}"
        )
    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=5)
    return child_address
