from __future__ import annotations

import asyncio
import uuid
from typing import Any, TypeVar

from uagents import Agent, Model
from uagents.dispatch import dispatcher
from uagents_adapter.mcp.protocol import CallTool, CallToolResponse, ListTools, ListToolsResponse

from .audit import AuditWriter
from .config import BridgeConfig
from .direct_protocol import build_protocol
from .mcp_shim import HermesMCPClientShim
from .registration_policies import NoopRegistrationPolicy

T = TypeVar("T", bound=Model)


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
    agent.include(build_protocol(shim, cfg, AuditWriter(cfg.audit_path)), publish_manifest=cfg.agent.publish_manifest)
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
    audit = AuditWriter(audit_path)
    async with HermesMCPClientShim(cfg) as shim:
        bridge = build_agent(cfg, shim)
        client_cfg = cfg.model_copy(deep=True)
        client_cfg.agent.name = cfg.agent.name + "_client"
        client = build_agent(client_cfg, shim)
        try:
            list_resp = await local_dispatch_request(bridge, client, ListTools(), ListToolsResponse)
            call_resp = await local_dispatch_request(
                bridge, client, CallTool(tool="echo", args={"text": "hello"}), CallToolResponse
            )
        finally:
            dispatcher.unregister(bridge.address, bridge)
            dispatcher.unregister(client.address, client)
    return bridge.address, len(list_resp.tools or []), str(call_resp.result), audit.count()


async def run_bridge(cfg: BridgeConfig) -> None:
    async with HermesMCPClientShim(cfg) as shim:
        agent = build_agent(cfg, shim)
        agent.run()
