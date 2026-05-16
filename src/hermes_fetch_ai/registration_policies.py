from __future__ import annotations

from typing import Any

from uagents_core.registration import AgentRegistrationPolicy


class NoopRegistrationPolicy(AgentRegistrationPolicy):
    async def register(
        self,
        agent_identifier: str,
        identity: Any,
        protocols: list[str],
        endpoints: list[Any],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        return None

    async def unregister(self, *args: Any, **kwargs: Any) -> None:
        return None

    def should_register(self, *args: Any, **kwargs: Any) -> bool:
        return False
