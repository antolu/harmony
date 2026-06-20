from __future__ import annotations

import abc
import dataclasses
import typing

import pydantic


@dataclasses.dataclass(frozen=True)
class ProviderJobSpec:
    entrypoint: str
    args: list[str]
    env: dict[str, str] = dataclasses.field(default_factory=dict)


class BaseProvider(abc.ABC):
    provider_type: typing.ClassVar[str]
    display_name: typing.ClassVar[str]
    description: typing.ClassVar[str]

    @classmethod
    @abc.abstractmethod
    def config_schema(cls) -> dict[str, pydantic.JsonValue]:
        """Return the JSON schema describing this provider's config."""

    @abc.abstractmethod
    def run(self) -> list[ProviderJobSpec]:
        """Return the job specs required to execute this provider."""
