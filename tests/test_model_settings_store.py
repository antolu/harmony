from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harmony.api.services.admin.model_settings import ModelSettingsStore


@pytest.fixture
def store() -> ModelSettingsStore:
    return ModelSettingsStore()


async def test_get_returns_default_when_no_db_row(store: ModelSettingsStore) -> None:
    mock_repo = AsyncMock()
    mock_repo.get.return_value = None
    mock_pool = MagicMock()
    mock_pool.connection.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_pool.connection.return_value.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "harmony.db.connection.get_async_pool", AsyncMock(return_value=mock_pool)
        ),
        patch(
            "harmony.api.services.admin.model_settings.ServiceConfigRepo",
            return_value=mock_repo,
        ),
    ):
        result = await store.get("reranker_provider")

    assert result == "ollama"


async def test_get_returns_db_value_over_default(store: ModelSettingsStore) -> None:
    mock_repo = AsyncMock()
    mock_repo.get.return_value = {"value": "litellm", "is_configured": True}
    mock_pool = MagicMock()
    mock_pool.connection.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_pool.connection.return_value.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "harmony.db.connection.get_async_pool", AsyncMock(return_value=mock_pool)
        ),
        patch(
            "harmony.api.services.admin.model_settings.ServiceConfigRepo",
            return_value=mock_repo,
        ),
    ):
        result = await store.get("reranker_provider")

    assert result == "litellm"


async def test_set_calls_repo_upsert(store: ModelSettingsStore) -> None:
    mock_repo = AsyncMock()
    mock_pool = MagicMock()
    mock_pool.connection.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_pool.connection.return_value.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "harmony.db.connection.get_async_pool", AsyncMock(return_value=mock_pool)
        ),
        patch(
            "harmony.api.services.admin.model_settings.ServiceConfigRepo",
            return_value=mock_repo,
        ),
    ):
        await store.set("reranker_provider", "litellm")

    mock_repo.upsert.assert_called_once_with(
        "reranker_provider", "litellm", None, validated=True
    )


async def test_get_all_returns_all_keys(store: ModelSettingsStore) -> None:
    mock_repo = AsyncMock()
    mock_repo.get.return_value = None
    mock_pool = MagicMock()
    mock_pool.connection.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_pool.connection.return_value.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "harmony.db.connection.get_async_pool", AsyncMock(return_value=mock_pool)
        ),
        patch(
            "harmony.api.services.admin.model_settings.ServiceConfigRepo",
            return_value=mock_repo,
        ),
    ):
        result = await store.get_all()

    expected_keys = {
        "embedding_provider",
        "embedding_model",
        "reranker_provider",
        "reranker_model",
        "llm_provider",
        "llm_model",
        "embedding_model_changed_since_last_embed",
    }
    assert set(result.keys()) == expected_keys
