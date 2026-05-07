from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harmony.api.services.admin.model_settings import ModelSettings, ModelSettingsStore


@pytest.fixture
def store() -> ModelSettingsStore:
    return ModelSettingsStore()


async def test_get_reranker_model_returns_default_when_no_db_row(
    store: ModelSettingsStore,
) -> None:
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
        result = await store.get_reranker_model()

    assert result == "ollama/bge-reranker-v2-m3"


async def test_get_reranker_model_returns_db_value(store: ModelSettingsStore) -> None:
    mock_repo = AsyncMock()
    mock_repo.get.return_value = {
        "value": "ollama/bge-reranker-v2-m3:latest",
        "is_configured": True,
    }
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
        result = await store.get_reranker_model()

    assert result == "ollama/bge-reranker-v2-m3:latest"


async def test_save_embedding_model_calls_upsert(store: ModelSettingsStore) -> None:
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
        await store.save_reranker_model("ollama/bge-reranker-v2-m3:latest")

    mock_repo.upsert.assert_called_once_with(
        "reranker_model", "ollama/bge-reranker-v2-m3:latest", None, validated=True
    )


async def test_get_all_returns_model_settings_dataclass(
    store: ModelSettingsStore,
) -> None:
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

    assert isinstance(result, ModelSettings)
    assert result.reranker_provider == "ollama"
    assert result.embedding_model_changed_since_last_embed is False


async def test_get_embedding_changed_returns_false_by_default(
    store: ModelSettingsStore,
) -> None:
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
        result = await store.get_embedding_changed()

    assert result is False


async def test_get_embedding_changed_returns_true_when_set(
    store: ModelSettingsStore,
) -> None:
    mock_repo = AsyncMock()
    mock_repo.get.return_value = {"value": "true", "is_configured": True}
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
        result = await store.get_embedding_changed()

    assert result is True
