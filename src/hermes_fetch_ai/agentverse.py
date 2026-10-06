"""Listing the bridge on Agentverse, so ASI:One users and other agents can reach it.

Registration goes through Agentverse's API with the owner's API key. It
proves the agent's identity by signing a challenge, and never spends from
the agent's wallet. The README written here is what ASI:One reads to decide
when to send a user to this agent.
"""

from __future__ import annotations

from collections.abc import Callable

from uagents import Protocol
from uagents_adapter.mcp.protocol import mcp_protocol_spec
from uagents_core.config import AgentverseConfig
from uagents_core.contrib.protocols.chat import chat_protocol_spec
from uagents_core.contrib.protocols.payment import payment_protocol_spec
from uagents_core.utils.registration import (
    AgentverseRegistrationRequest,
    RegistrationRequestCredentials,
    register_agent,
)

from .chat_menu import price_text
from .config import BridgeConfig

API_KEY_VAR = "AGENTVERSE_API_KEY"

Register = Callable[
    [AgentverseRegistrationRequest, AgentverseConfig, RegistrationRequestCredentials], bool
]


def protocol_digests(cfg: BridgeConfig | None = None) -> list[str]:
    """The protocols the bridge speaks: chat, payment (as seller, buyer, or both), and MCP."""
    selling = cfg is None or bool(cfg.services)
    digests = [Protocol(spec=chat_protocol_spec).digest]
    if selling:
        digests.append(Protocol(spec=payment_protocol_spec, role="seller").digest)
    if cfg is not None and cfg.buying.enabled:
        digests.append(Protocol(spec=payment_protocol_spec, role="buyer").digest)
    digests.append(Protocol(spec=mcp_protocol_spec, role="server").digest)
    return digests


def readme(cfg: BridgeConfig) -> str:
    """The agent's Agentverse README: what it sells, at what price, and how to order."""
    services = cfg.services
    if not services:
        return "\n".join(
            [
                f"# {cfg.agent.name}",
                "",
                cfg.agent.description,
                "",
                (
                    "A Hermes agent on Fetch.ai's Dorado test network. It buys services from "
                    "other agents for its owner, who approves every payment; it sells nothing."
                ),
                "",
            ]
        )
    example = next(iter(services), "service")
    lines = [
        f"# {cfg.agent.name}",
        "",
        cfg.agent.description,
        "",
        "A Hermes agent that sells services for testnet FET on Fetch.ai's Dorado test network.",
        "",
        "## Services",
        "",
    ]
    lines += [
        f"- **{svc.title}** (`{name}`), {price_text(svc)}: {svc.description}"
        for name, svc in services.items()
    ]
    lines += [
        "",
        "## How to order",
        "",
        "Send a message that starts with the service name, then your request:",
        "",
        f"`{example}: <your request>`",
        "",
        (
            "Any other message gets the list of services and prices. Before anything runs "
            "you are asked to approve a testnet FET payment; the last digits of the amount "
            "are the order's code."
        ),
        "",
        "## Payments",
        "",
        (
            "Testnet FET only (Dorado). The agent checks every payment on the ledger itself, "
            "and each payment buys one request."
        ),
        "",
        "## Limitations",
        "",
        (
            "- Answers come from the seller's own programs and models; check them before "
            "relying on them."
        ),
    ]
    lines += [f"- {svc.title}: {svc.disclaimer}" for svc in services.values() if svc.disclaimer]
    return "\n".join(lines) + "\n"


def registration(cfg: BridgeConfig) -> AgentverseRegistrationRequest:
    """What to register: the agent's name, how it is reached, its protocols and README."""
    mailbox = cfg.agent.mode == "mailbox"
    if mailbox:
        endpoint = AgentverseConfig().mailbox_endpoint
    elif cfg.agent.endpoint:
        endpoint = cfg.agent.endpoint
    else:
        raise ValueError(
            "Agentverse needs to reach the agent: set agent.mode: mailbox, or set "
            "agent.endpoint to a public https:// address"
        )
    first = next(iter(cfg.services), None)
    return AgentverseRegistrationRequest(
        name=cfg.agent.name,
        endpoint=endpoint,
        protocols=protocol_digests(cfg),
        type="mailbox" if mailbox else "uagent",
        description=cfg.agent.description,
        readme=readme(cfg),
        handle=cfg.agent.handle,
        starter_prompts=(
            ["What services do you offer, and what do they cost?", f"{first}: <your request>"]
            if first
            else None  # it sells nothing, so there is nothing to ask it for
        ),
        active=True,
    )


def register(
    cfg: BridgeConfig, seed: str, api_key: str, *, register_fn: Register | None = None
) -> AgentverseRegistrationRequest:
    """Register (or update) the agent on Agentverse; raises on failure."""
    request = registration(cfg)
    (register_fn or register_agent)(
        request,
        AgentverseConfig(),
        RegistrationRequestCredentials(agentverse_api_key=api_key, agent_seed_phrase=seed),
    )
    return request
