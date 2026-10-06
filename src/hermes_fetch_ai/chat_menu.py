"""The words a chat buyer sees: the service menu, and how a message picks a service.

Chat buyers, such as ASI:One users, write plain text. A message orders a
service by starting with the service's name or title, followed by the
request: "security-review: <code>". Anything else gets the menu.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from .config import ServiceConfig
from .money import format_fet

# Characters that may separate a service name from the request.
_SEPARATORS = ":-–—\n\t "
_MENTION = re.compile(r"^@[\w.-]+[,:]?\s*")


def price_text(svc: ServiceConfig) -> str:
    return f"{format_fet(svc.price_base)} testnet FET" if svc.price_base else "free"


def menu(agent_name: str, services: Mapping[str, ServiceConfig]) -> str:
    """The plain-language menu of services and prices, in Markdown."""
    lines = [
        (
            f"Hi! I'm {agent_name}, a Hermes agent. I sell these services, paid in testnet FET "
            "(Fetch.ai's test network: test money with no value):"
        ),
        "",
    ]
    for number, (name, svc) in enumerate(services.items(), start=1):
        lines.append(f"{number}. **{svc.title}** (`{name}`), {price_text(svc)}")
        lines.append(f"   {svc.description}")
    example = next(iter(services), "service")
    lines += [
        "",
        "To order, start your message with the service name, then your request, for example:",
        f"`{example}: <your request>`",
        "You will be asked to approve the payment before anything runs.",
    ]
    return "\n".join(lines)


def pick_service(text: str, services: Mapping[str, ServiceConfig]) -> tuple[str, str] | None:
    """The service a message orders and its request, or None if it names none.

    The name or title must come first, followed by a separator or the end of
    the message. Longer names are tried first, so "review-pro" wins over
    "review". The request may be empty; the caller asks for it.
    """
    # ASI:One users address an agent as @handle or @agent1...; that is not part of the order.
    stripped = _MENTION.sub("", text.strip(), count=1).strip()
    lowered = stripped.lower()
    labels = sorted(
        ((label, name) for name, svc in services.items() for label in (name, svc.title)),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )
    for label, name in labels:
        if not lowered.startswith(label.lower()):
            continue
        rest = stripped[len(label) :]
        if rest and rest[0] not in _SEPARATORS:
            continue  # "reviewer" does not order "review"
        return name, rest.lstrip(_SEPARATORS).strip()
    return None


def ask_for_request(name: str, svc: ServiceConfig) -> str:
    return (
        f"**{svc.title}** ({price_text(svc)}): {svc.description}\n\n"
        f"Send your request after the service name, for example `{name}: <your request>`."
    )
