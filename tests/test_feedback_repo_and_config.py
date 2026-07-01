from __future__ import annotations

import typing
from unittest.mock import AsyncMock, MagicMock

from harmony.db.repositories import MessageFeedbackRepo  # type: ignore[attr-defined]
from harmony.services.admin import ServiceConfigStore


def _make_pool() -> tuple[typing.Any, typing.Any, typing.Any]:
    cursor = AsyncMock()

    cursor_cm = MagicMock()
    cursor_cm.__aenter__ = AsyncMock(return_value=cursor)
    cursor_cm.__aexit__ = AsyncMock(return_value=False)

    conn = MagicMock()
    conn.cursor.return_value = cursor_cm
    conn.set_autocommit = AsyncMock()
    conn.execute = AsyncMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)

    conn_cm = MagicMock()
    conn_cm.__aenter__ = AsyncMock(return_value=conn)
    conn_cm.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.connection.return_value = conn_cm

    return pool, conn, cursor


async def test_message_feedback_repo_upsert_calls_execute() -> None:
    pool, conn, _cursor = _make_pool()
    repo = MessageFeedbackRepo(pool)
    await repo.upsert("conv-1", 42, "user-1", "up")
    conn.execute.assert_called_once()
    sql = conn.execute.call_args[0][0]
    assert "ON CONFLICT" in sql
    assert "DO UPDATE" in sql
    assert "rating" in sql.lower()


async def test_message_feedback_repo_upsert_passes_correct_params() -> None:
    pool, conn, _cursor = _make_pool()
    repo = MessageFeedbackRepo(pool)
    await repo.upsert("conv-1", 42, "user-1", "down")
    call_args = conn.execute.call_args[0]
    params = call_args[1]
    assert "conv-1" in params
    assert 42 in params
    assert "user-1" in params
    assert "down" in params


def _make_description(cols: list[str]) -> list[MagicMock]:
    mocks = []
    for col in cols:
        m = MagicMock()
        m.name = col
        mocks.append(m)
    return mocks


async def test_message_feedback_repo_get_for_conversation_returns_list() -> None:
    pool, _conn, cursor = _make_pool()
    from datetime import datetime

    now = datetime.now()
    cursor.description = _make_description([
        "id",
        "conversation_id",
        "message_id",
        "user_id",
        "rating",
        "created_at",
        "updated_at",
    ])
    cursor.fetchall = AsyncMock(
        return_value=[
            (1, "conv-1", 42, "user-1", "up", now, now),
        ]
    )
    repo = MessageFeedbackRepo(pool)
    result = await repo.get_for_conversation("conv-1", "user-1")
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["conversation_id"] == "conv-1"
    assert result[0]["rating"] == "up"


async def test_message_feedback_repo_get_for_conversation_scoped_to_user() -> None:
    pool, _conn, cursor = _make_pool()
    cursor.description = _make_description([
        "id",
        "conversation_id",
        "message_id",
        "user_id",
        "rating",
        "created_at",
        "updated_at",
    ])
    cursor.fetchall = AsyncMock(return_value=[])
    repo = MessageFeedbackRepo(pool)
    await repo.get_for_conversation("conv-1", "user-1")
    sql = cursor.execute.call_args[0][0]
    params = cursor.execute.call_args[0][1]
    assert "user_id" in sql
    assert "user-1" in params


async def test_message_feedback_repo_delete_user_rating_calls_execute() -> None:
    pool, conn, _cursor = _make_pool()
    repo = MessageFeedbackRepo(pool)
    await repo.delete_user_rating("conv-1", 42, "user-1")
    conn.execute.assert_called_once()
    sql = conn.execute.call_args[0][0]
    assert "DELETE" in sql.upper()
    assert "message_feedback" in sql


def test_service_config_store_has_feedback_enabled_default() -> None:
    store = ServiceConfigStore()
    assert "feedback_enabled" in store.DEFAULTS
    assert store.DEFAULTS["feedback_enabled"] == "true"


def test_service_config_store_has_feedback_enabled_description() -> None:
    store = ServiceConfigStore()
    assert "feedback_enabled" in store.DESCRIPTIONS
