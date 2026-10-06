from __future__ import annotations

from typing import Any

from uagents_core.registration import AgentRegistrationPolicy


class NoopRegistrationPolicy(AgentRegistrationPolicy):
    """Registers nowhere, for a bridge with ``publish_manifest: false``."""

    async def register(
        self,
        agent_identifier: str,
        identity: Any,
        protocols: list[str],
        endpoints: list[Any],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        return None
