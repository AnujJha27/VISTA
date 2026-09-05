from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .agents import AgentSpec
from .providers import LlmProvider


@dataclass(slots=True)
class ProviderRouter:
    default_provider: LlmProvider

    def complete(self, agent: AgentSpec, *, system: str, prompt: str,
                 schema: dict[str, Any]) -> dict[str, Any]:
        return self.default_provider.complete(
            agent=agent.name,
            system=system,
            prompt=prompt,
            schema=schema,
        )
