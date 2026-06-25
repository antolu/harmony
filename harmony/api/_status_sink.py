from __future__ import annotations

import asyncio
import dataclasses
from collections.abc import AsyncIterator

import pydantic

_SENTINEL: object = object()


@dataclasses.dataclass
class StatusEvent:
    message: str
    metadata: dict[str, pydantic.JsonValue]


class StatusSink:
    """Request-scoped, in-process event sink decoupled from the call stack.

    Ordered pass-through over an asyncio.Queue: one delivered item per emit()
    call, no pacing/coalescing.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[StatusEvent | object] = asyncio.Queue()

    def emit(self, message: str, **metadata: pydantic.JsonValue) -> None:
        self._queue.put_nowait(StatusEvent(message=message, metadata=metadata))

    def close(self) -> None:
        self._queue.put_nowait(_SENTINEL)

    async def drain(self) -> AsyncIterator[StatusEvent]:
        while True:
            item = await self._queue.get()
            if not isinstance(item, StatusEvent):
                return
            yield item
