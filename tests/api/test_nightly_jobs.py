from __future__ import annotations

import inspect
import typing
from unittest.mock import AsyncMock, MagicMock

import pytest

from harmony.api.main import nightly_audit_cleanup, nightly_conversation_cleanup


@pytest.mark.asyncio
async def test_nightly_audit_cleanup_uses_app_state_directly() -> None:
    mock_app_state = MagicMock()
    mock_app_state.service_config_store.get = AsyncMock(return_value="30")
    mock_app_state.audit_log_service.cleanup_audit_events = AsyncMock(return_value=5)

    await nightly_audit_cleanup(mock_app_state)

    mock_app_state.audit_log_service.cleanup_audit_events.assert_awaited_once_with(30)
    assert "from harmony.api.main import app" not in inspect.getsource(
        nightly_audit_cleanup
    )


@pytest.mark.asyncio
async def test_nightly_conversation_cleanup_uses_app_state_directly() -> None:
    mock_app_state = MagicMock()
    mock_app_state.service_config_store.get = AsyncMock(return_value="10")
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_cursor = AsyncMock()
    mock_cursor.rowcount = 3
    mock_cursor_cm = MagicMock()
    mock_cursor_cm.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor_cm.__aexit__ = AsyncMock(return_value=None)
    mock_conn.cursor = MagicMock(return_value=mock_cursor_cm)
    mock_conn_cm = MagicMock()
    mock_conn_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn_cm.__aexit__ = AsyncMock(return_value=None)
    mock_pool.connection = MagicMock(return_value=mock_conn_cm)
    mock_app_state.db_pool = mock_pool

    await nightly_conversation_cleanup(mock_app_state)

    mock_cursor.execute.assert_awaited_once()
    assert "from harmony.api.main import app" not in inspect.getsource(
        nightly_conversation_cleanup
    )


def test_nightly_audit_cleanup_app_state_not_typing_any() -> None:
    sig = inspect.signature(nightly_audit_cleanup)
    param = sig.parameters["app_state"]
    assert param.annotation is not typing.Any
    assert param.default is inspect.Parameter.empty


def test_nightly_conversation_cleanup_app_state_not_typing_any() -> None:
    sig = inspect.signature(nightly_conversation_cleanup)
    param = sig.parameters["app_state"]
    assert param.annotation is not typing.Any
    assert param.default is inspect.Parameter.empty
