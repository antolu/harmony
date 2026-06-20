from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pydantic
import structlog
from litellm.integrations.custom_logger import CustomLogger
from litellm.types.utils import ModelResponse

from harmony.db.repositories import TokenUsageRepo

if TYPE_CHECKING:
    import psycopg_pool


class UsageCallback(CustomLogger):
    def __init__(self) -> None:
        super().__init__()
        self._queue: asyncio.Queue[dict[str, pydantic.JsonValue]] = asyncio.Queue()

    def get_usage_queue(self) -> asyncio.Queue[dict[str, pydantic.JsonValue]]:
        return self._queue

    async def async_log_success_event(
        self,
        kwargs: dict[str, pydantic.JsonValue],
        response_obj: ModelResponse,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        try:
            event = _build_token_event(kwargs, response_obj)
            await self._queue.put(event)
        except Exception as e:
            structlog.get_logger().warning("token_tracking_failure", error=str(e))


_CONSUMER_BATCH_SIZE = 100
_CONSUMER_INTERVAL_SECS = 5


def _build_token_event(
    kwargs: dict[str, pydantic.JsonValue], response_obj: ModelResponse
) -> dict[str, pydantic.JsonValue]:
    litellm_params = kwargs.get("litellm_params") or {}
    metadata_raw = (
        litellm_params.get("metadata") if isinstance(litellm_params, dict) else None
    )
    metadata: dict[str, pydantic.JsonValue] = (
        metadata_raw if isinstance(metadata_raw, dict) else {}
    )
    model: str = str(kwargs.get("model") or "")
    usage = getattr(response_obj, "usage", None)
    return {
        "trace_id": metadata.get("trace_id", ""),
        "user_id": metadata.get("user_id", ""),
        "endpoint": metadata.get("endpoint", ""),
        "agent_step": metadata.get("agent_step", ""),
        "model": model,
        "provider": model.split("/", maxsplit=1)[0] if "/" in model else "",
        "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
        "recorded_at": datetime.now(UTC).isoformat(),
    }


def _drain_batch(
    queue: asyncio.Queue[dict[str, pydantic.JsonValue]],
) -> list[dict[str, pydantic.JsonValue]]:
    batch: list[dict[str, pydantic.JsonValue]] = []
    while len(batch) < _CONSUMER_BATCH_SIZE:
        try:
            batch.append(queue.get_nowait())
        except asyncio.QueueEmpty:
            break
    return batch


def start_queue_consumer(
    queue: asyncio.Queue[dict[str, pydantic.JsonValue]],
    pool: psycopg_pool.AsyncConnectionPool,
) -> asyncio.Task:
    async def _consumer() -> None:
        repo = TokenUsageRepo(pool)
        log = structlog.get_logger(__name__)
        while True:
            await asyncio.sleep(_CONSUMER_INTERVAL_SECS)
            try:
                batch = _drain_batch(queue)
                if batch:
                    await repo.insert_batch(batch)
            except Exception as exc:
                log.warning("token_consumer_error", error=str(exc))

    return asyncio.ensure_future(_consumer())
