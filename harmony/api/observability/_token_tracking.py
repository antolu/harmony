from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog
from litellm.integrations.custom_logger import CustomLogger


class TokenUsageEvent(dict):
    pass


class UsageCallback(CustomLogger):
    def __init__(self) -> None:
        super().__init__()
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    def get_usage_queue(self) -> asyncio.Queue[dict[str, Any]]:
        return self._queue

    async def async_log_success_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: Any,
        end_time: Any,
    ) -> None:
        try:
            metadata = kwargs.get("litellm_params", {}).get("metadata", {}) or {}
            trace_id: str = metadata.get("trace_id", "")
            user_id: str = metadata.get("user_id", "")
            endpoint: str = metadata.get("endpoint", "")
            agent_step: str = metadata.get("agent_step", "")
            model: str = kwargs.get("model", "") or ""

            provider = model.split("/", maxsplit=1)[0] if "/" in model else ""

            usage = getattr(response_obj, "usage", None)
            input_tokens = getattr(usage, "prompt_tokens", 0) or 0
            output_tokens = getattr(usage, "completion_tokens", 0) or 0
            total_tokens = getattr(usage, "total_tokens", 0) or 0

            event: dict[str, Any] = {
                "trace_id": trace_id,
                "user_id": user_id,
                "endpoint": endpoint,
                "agent_step": agent_step,
                "model": model,
                "provider": provider,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "recorded_at": datetime.now(UTC).isoformat(),
            }
            await self._queue.put(event)
        except Exception as e:
            structlog.get_logger().warning("token_tracking_failure", error=str(e))
