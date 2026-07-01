from __future__ import annotations

import asyncio
import typing
from unittest.mock import AsyncMock, patch

import pytest

from harmony.services.admin import ModelSettings, ModelSettingsStore


@pytest.fixture
def store() -> ModelSettingsStore:
    return ModelSettingsStore()


def _make_pool_getter(pool: object) -> typing.Any:
    async def _get() -> object:
        await asyncio.sleep(0)
        return pool

    return _get


async def test_get_reranker_model_returns_default_when_no_db_row(
    store: ModelSettingsStore,
) -> None:
    mock_repo = AsyncMock()
    mock_repo.get.return_value = None
    mock_pool = object()

    with (
        patch(
            "harmony.services.admin._model_settings.get_async_pool",
            _make_pool_getter(mock_pool),
        ),
        patch(
            "harmony.services.admin._model_settings.ServiceConfigRepo",
            return_value=mock_repo,
        ),
    ):
        result = await store.get_reranker_model()

    assert result == "ollama/bge-reranker-v2-m3"


async def test_get_reranker_model_returns_db_value(store: ModelSettingsStore) -> None:
    import datetime

    from harmony.db.repositories import ServiceConfigData

    mock_repo = AsyncMock()
    mock_repo.get.return_value = ServiceConfigData(
        key="reranker_model",
        value="ollama/bge-reranker-v2-m3:latest",
        is_configured=True,
        description="",
        validated_at=datetime.datetime.now(datetime.UTC).isoformat(),
        updated_at=datetime.datetime.now(datetime.UTC).isoformat(),
    )
    mock_pool = object()

    with (
        patch(
            "harmony.services.admin._model_settings.get_async_pool",
            _make_pool_getter(mock_pool),
        ),
        patch(
            "harmony.services.admin._model_settings.ServiceConfigRepo",
            return_value=mock_repo,
        ),
    ):
        result = await store.get_reranker_model()

    assert result == "ollama/bge-reranker-v2-m3:latest"


async def test_save_embedding_model_calls_upsert(store: ModelSettingsStore) -> None:
    mock_repo = AsyncMock()
    mock_pool = object()

    with (
        patch(
            "harmony.services.admin._model_settings.get_async_pool",
            _make_pool_getter(mock_pool),
        ),
        patch(
            "harmony.services.admin._model_settings.ServiceConfigRepo",
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
    mock_pool = object()

    with (
        patch(
            "harmony.services.admin._model_settings.get_async_pool",
            _make_pool_getter(mock_pool),
        ),
        patch(
            "harmony.services.admin._model_settings.ServiceConfigRepo",
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
    mock_pool = object()

    with (
        patch(
            "harmony.services.admin._model_settings.get_async_pool",
            _make_pool_getter(mock_pool),
        ),
        patch(
            "harmony.services.admin._model_settings.ServiceConfigRepo",
            return_value=mock_repo,
        ),
    ):
        result = await store.get_embedding_changed()

    assert result is False


async def test_get_embedding_changed_returns_true_when_set(
    store: ModelSettingsStore,
) -> None:
    import datetime

    from harmony.db.repositories import ServiceConfigData

    mock_repo = AsyncMock()
    mock_repo.get.return_value = ServiceConfigData(
        key="embedding_model_changed_since_last_embed",
        value="true",
        is_configured=True,
        description="",
        validated_at=datetime.datetime.now(datetime.UTC).isoformat(),
        updated_at=datetime.datetime.now(datetime.UTC).isoformat(),
    )
    mock_pool = object()

    with (
        patch(
            "harmony.services.admin._model_settings.get_async_pool",
            _make_pool_getter(mock_pool),
        ),
        patch(
            "harmony.services.admin._model_settings.ServiceConfigRepo",
            return_value=mock_repo,
        ),
    ):
        result = await store.get_embedding_changed()

    assert result is True
