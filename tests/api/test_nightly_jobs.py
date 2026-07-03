from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest

from harmony.api._bootstrap import nightly_audit_cleanup, nightly_conversation_cleanup


@pytest.mark.asyncio
async def test_nightly_audit_cleanup_uses_app_state_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that nightly_audit_cleanup is self-contained and constructs its own services."""
    mock_pool = MagicMock()
    mock_service_config = MagicMock()
    mock_audit_log_service = MagicMock()

    mock_service_config.initialize = AsyncMock(return_value=None)
    mock_service_config.get = AsyncMock(return_value="30")
    mock_audit_log_service.initialize = AsyncMock(return_value=None)
    mock_audit_log_service.cleanup_audit_events = AsyncMock(return_value=5)

    async def mock_get_async_pool() -> MagicMock:
        return mock_pool

    monkeypatch.setattr(
        "harmony.api._bootstrap._maintenance.get_async_pool", mock_get_async_pool
    )
    monkeypatch.setattr(
        "harmony.api._bootstrap._maintenance.ServiceConfigStore",
        lambda: mock_service_config,
    )
    monkeypatch.setattr(
        "harmony.api._bootstrap._maintenance.AuditLogService",
        lambda: mock_audit_log_service,
    )

    await nightly_audit_cleanup()

    mock_audit_log_service.cleanup_audit_events.assert_awaited_once_with(30)
    assert "from harmony.api.main import app" not in inspect.getsource(
        nightly_audit_cleanup
    )


@pytest.mark.asyncio
async def test_nightly_conversation_cleanup_uses_app_state_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that nightly_conversation_cleanup is self-contained and constructs its own services."""
    mock_pool = MagicMock()
    mock_service_config = MagicMock()
    mock_cursor = AsyncMock()
    mock_cursor.rowcount = 3
    mock_cursor_cm = MagicMock()
    mock_cursor_cm.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor_cm.__aexit__ = AsyncMock(return_value=None)
    mock_conn = AsyncMock()
    mock_conn.cursor = MagicMock(return_value=mock_cursor_cm)
    mock_conn.set_autocommit = AsyncMock(return_value=None)
    mock_conn_cm = MagicMock()
    mock_conn_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn_cm.__aexit__ = AsyncMock(return_value=None)
    mock_pool.connection = MagicMock(return_value=mock_conn_cm)

    mock_service_config.initialize = AsyncMock(return_value=None)
    mock_service_config.get = AsyncMock(return_value="10")

    async def mock_get_async_pool() -> MagicMock:
        return mock_pool

    monkeypatch.setattr(
        "harmony.api._bootstrap._maintenance.get_async_pool", mock_get_async_pool
    )
    monkeypatch.setattr(
        "harmony.api._bootstrap._maintenance.ServiceConfigStore",
        lambda: mock_service_config,
    )

    await nightly_conversation_cleanup()

    mock_cursor.execute.assert_awaited_once()
    assert "from harmony.api.main import app" not in inspect.getsource(
        nightly_conversation_cleanup
    )


def test_nightly_audit_cleanup_has_no_parameters() -> None:
    """Test that nightly_audit_cleanup takes no parameters (self-contained)."""
    sig = inspect.signature(nightly_audit_cleanup)
    assert len(sig.parameters) == 0


def test_nightly_conversation_cleanup_has_no_parameters() -> None:
    """Test that nightly_conversation_cleanup takes no parameters (self-contained)."""
    sig = inspect.signature(nightly_conversation_cleanup)
    assert len(sig.parameters) == 0
