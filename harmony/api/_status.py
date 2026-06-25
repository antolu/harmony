from __future__ import annotations

import typing

import pydantic


class StatusSinkProtocol(typing.Protocol):
    """Structural contract for status reporting.

    Agents and tools depend on this, not on any concrete sink
    implementation, so they can run outside the Harmony API/web process
    (scripts, tests, other host services) without importing request/queue
    machinery they'll never use.
    """

    def emit(self, message: str, **metadata: pydantic.JsonValue) -> None: ...
