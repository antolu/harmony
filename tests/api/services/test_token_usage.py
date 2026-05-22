from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch


def test_usage_query_groups_by_model_user_date() -> None:
    """TOKEN-01: Usage records group by model, user, date."""
    from harmony.db.repositories import TokenUsageRepo

    pool = MagicMock()
    repo = TokenUsageRepo(pool)

    conn_cm = AsyncMock()
    cur_cm = AsyncMock()

    aggregated_row = ("u1", "gpt-4", "2026-05-22", 300, 130, 430)

    cur_cm.__aenter__ = AsyncMock(return_value=cur_cm)
    cur_cm.__aexit__ = AsyncMock(return_value=None)
    cur_cm.execute = AsyncMock()
    cur_cm.fetchall = AsyncMock(return_value=[aggregated_row])
    cur_cm.description = None

    conn_cm.__aenter__ = AsyncMock(return_value=conn_cm)
    conn_cm.__aexit__ = AsyncMock(return_value=None)
    conn_cm.cursor = MagicMock(return_value=cur_cm)

    pool.connection = MagicMock(return_value=conn_cm)

    result = asyncio.get_event_loop().run_until_complete(repo.query())

    assert len(result) == 1
    row = result[0]
    assert row["user_id"] == "u1"
    assert row["model"] == "gpt-4"
    assert row["total_tokens"] == 430

    sql_call = cur_cm.execute.call_args[0][0]
    assert "GROUP BY" in sql_call.upper()
    assert "DATE" in sql_call.upper()


def test_litellm_callback_emits_usage_event_async() -> None:
    """TOKEN-02: LiteLLM callback queues usage event asynchronously."""
    from harmony.api.observability import UsageCallback

    callback = UsageCallback()
    queue = callback.get_usage_queue()

    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 20
    usage.total_tokens = 30

    response_obj = MagicMock()
    response_obj.usage = usage

    kwargs: dict[str, Any] = {
        "model": "gpt-4",
        "litellm_params": {
            "metadata": {
                "trace_id": "t1",
                "user_id": "u1",
                "endpoint": "/search",
                "agent_step": "step1",
            }
        },
    }

    asyncio.get_event_loop().run_until_complete(
        callback.async_log_success_event(
            kwargs=kwargs,
            response_obj=response_obj,
            start_time=None,
            end_time=None,
        )
    )

    assert not queue.empty()
    event = queue.get_nowait()
    assert event["model"] == "gpt-4"
    assert event["input_tokens"] == 10
    assert event["total_tokens"] == 30
    assert event["trace_id"] == "t1"


def test_tracking_failure_does_not_block_response() -> None:
    """TOKEN-02: A failure in usage tracking does not propagate to the API response."""
    from harmony.api.observability import UsageCallback

    callback = UsageCallback()

    with patch.object(callback._queue, "put", side_effect=RuntimeError("queue full")):
        exc = None
        try:
            asyncio.get_event_loop().run_until_complete(
                callback.async_log_success_event(
                    kwargs={"model": "gpt-4", "litellm_params": {}},
                    response_obj=MagicMock(usage=None),
                    start_time=None,
                    end_time=None,
                )
            )
        except Exception as e:
            exc = e

        assert exc is None, f"Exception propagated: {exc}"
