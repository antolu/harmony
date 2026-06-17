from __future__ import annotations

import dataclasses
import typing
from abc import ABC, abstractmethod


@dataclasses.dataclass(frozen=True)
class ProviderJobSpec:
    entrypoint: str
    args: list[str]
    env: dict[str, str] = dataclasses.field(default_factory=dict)


class BaseProvider(ABC):
    provider_type: typing.ClassVar[str]
    display_name: typing.ClassVar[str]
    description: typing.ClassVar[str]

    @classmethod
    @abstractmethod
    def config_schema(cls) -> dict[str, typing.Any]:
        """Return the JSON schema describing this provider's config."""

    @abstractmethod
    def run(self) -> list[ProviderJobSpec]:
        """Return the job specs required to execute this provider."""
