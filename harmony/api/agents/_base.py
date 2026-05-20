from __future__ import annotations

import typing
from abc import ABC, abstractmethod

from pydantic import BaseModel


class AgentCapability(BaseModel):
    name: str
    description: str
    cost: float = 1.0


class AgentResult(BaseModel):
    content: str
    metadata: dict[str, typing.Any]
    confidence: float = 1.0


class BaseAgent(ABC):
    def __init__(self) -> None:
        self.name: str = ""
        self.capability: AgentCapability = AgentCapability(
            name="",
            description="",
            cost=1.0,
        )

    @abstractmethod
    async def execute(self, task: dict[str, typing.Any]) -> AgentResult:
        """Execute the agent's task and return result."""

    def get_capability_embedding(self) -> list[float]:
        """Return embedding of agent's capability description.

        To be implemented by subclasses if capability matching is needed.
        """
        return []
