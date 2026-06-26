from __future__ import annotations

import abc
import typing

import pydantic
from pydantic import BaseModel

from harmony.api._status import StatusSinkProtocol

AgentTask = typing.TypeVar("AgentTask", bound=BaseModel)


class AgentCapability(BaseModel):
    name: str
    description: str
    cost: float = 1.0


class AgentResult(BaseModel):
    content: str
    metadata: dict[str, pydantic.JsonValue]
    confidence: float = 1.0


class BaseAgent(abc.ABC, typing.Generic[AgentTask]):
    def __init__(self) -> None:
        self.name: str = ""
        self.capability: AgentCapability = AgentCapability(
            name="",
            description="",
            cost=1.0,
        )

    @abc.abstractmethod
    async def execute(self, task: AgentTask, sink: StatusSinkProtocol) -> AgentResult:
        """Execute the agent's task and return result."""

    def get_capability_embedding(self) -> list[float]:
        """Return embedding of agent's capability description.

        To be implemented by subclasses if capability matching is needed.
        """
        return []
