from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harmony.api._bootstrap import (
    init_core_services,
    init_db,
    init_search_service,
)
from harmony.api._config import Settings
from harmony.services import PipelineConfig
from harmony.services.admin import ModelSettingsStore


@pytest.mark.asyncio
async def test_model_settings_store_constructed_once_before_search_service() -> None:
    """ModelSettingsStore must be constructed once and shared by all consumption points
    (LLMService, HarmonyVectorBackend, HarmonyRerankerBackend)."""
    settings = Settings(cors_allowed_origins="http://localhost")

    mock_pool = MagicMock()
    mock_secret_service = AsyncMock()

    with (
        patch(
            "harmony.api._bootstrap._db.get_async_pool",
            AsyncMock(return_value=mock_pool),
        ),
        patch(
            "harmony.api._bootstrap._db.ServiceConfigStore.initialize",
            AsyncMock(return_value=None),
        ),
        patch(
            "harmony.api._bootstrap._db.ServiceConfigStore.get",
            AsyncMock(return_value=None),
        ),
        patch(
            "harmony.api._bootstrap._db.ServiceConfigStore.get_status",
            AsyncMock(return_value={}),
        ),
        patch(
            "harmony.api._bootstrap._db.SecretValueService.from_env_or_db",
            AsyncMock(return_value=mock_secret_service),
        ),
        patch("harmony.api._bootstrap._db.ModelPolicyStore", MagicMock()),
    ):
        db = await init_db(settings)

    assert isinstance(db.model_settings_store, ModelSettingsStore)

    with (
        patch(
            "harmony.api._bootstrap._core.ConversationService",
            MagicMock(),
        ),
        patch(
            "harmony.api._bootstrap._search.HarmonyKeywordBackend",
            MagicMock(),
        ),
        patch(
            "harmony.api._bootstrap._search.load_pipeline_config",
            AsyncMock(return_value=PipelineConfig()),
        ),
        patch("harmony.api._bootstrap._core.PromptManager"),
    ):
        await init_core_services(
            db.service_config,
            db.model_policy_store,
            mock_pool,
            settings,
        )
        search = await init_search_service(
            db.service_config,
            db.model_settings_store,
            settings,
            None,
            MagicMock(),
            db.secret_service,
        )

    search_service = search.search_service
    assert search_service._vector_backend is not None
    assert search_service._reranker_backend is not None
    assert (
        search_service._vector_backend._model_settings_store is db.model_settings_store
    )
    assert (
        search_service._reranker_backend._model_settings_store
        is db.model_settings_store
    )
