from __future__ import annotations

import asyncio
import typing
from collections.abc import AsyncIterator

from harmony.models import StatusEvent

_SENTINEL: object = object()


class StatusSink:
    """Request-scoped, in-process event sink decoupled from the call stack.

    Ordered pass-through over an asyncio.Queue: one delivered item per emit()
    call, no pacing/coalescing.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[StatusEvent | object] = asyncio.Queue()

    def emit(self, event: StatusEvent) -> None:
        self._queue.put_nowait(event)

    def close(self) -> None:
        self._queue.put_nowait(_SENTINEL)

    async def drain(self) -> AsyncIterator[StatusEvent]:
        while True:
            item = await self._queue.get()
            if item is _SENTINEL:
                return
            yield typing.cast("StatusEvent", item)


class NullSink:
    """No-op sink for callers outside an HTTP request scope.

    Used where nothing will ever drain a real StatusSink (orchestrator call
    sites not yet wired to a request sink, scripts, tests).
    """

    def emit(self, event: StatusEvent) -> None:
        pass


null_sink = NullSink()
