from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harmony.api.config import Settings
from harmony.api.main import (
    _init_core_services,
    _init_db,
    _init_search_service,
)
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
            "harmony.api.main.get_async_pool",
            AsyncMock(return_value=mock_pool),
        ),
        patch(
            "harmony.api.main.ServiceConfigStore.initialize",
            AsyncMock(return_value=None),
        ),
        patch(
            "harmony.api.main.ServiceConfigStore.get",
            AsyncMock(return_value=None),
        ),
        patch(
            "harmony.api.main.ServiceConfigStore.get_status",
            AsyncMock(return_value={}),
        ),
        patch(
            "harmony.api.main.SecretValueService.from_env_or_db",
            AsyncMock(return_value=mock_secret_service),
        ),
        patch("harmony.api.main.ModelPolicyStore", MagicMock()),
    ):
        (
            _pool,
            service_config,
            model_settings_store,
            secret_service,
            model_policy_store,
        ) = await _init_db(settings)

    assert isinstance(model_settings_store, ModelSettingsStore)

    with (
        patch(
            "harmony.api.main.ElasticsearchService.health_check",
            AsyncMock(return_value=True),
        ),
        patch("harmony.api.main.QdrantService", side_effect=Exception("unavailable")),
        patch(
            "harmony.api.main.ConversationService",
            MagicMock(),
        ),
        patch(
            "harmony.api.main.HarmonyKeywordBackend",
            MagicMock(),
        ),
        patch(
            "harmony.api.main.load_pipeline_config",
            AsyncMock(return_value=PipelineConfig()),
        ),
        patch("harmony.api.main.PromptManager"),
    ):
        await _init_core_services(
            service_config,
            model_policy_store,
            mock_pool,
            settings,
        )
        (
            _pipeline_config,
            _keyword_backend,
            _external_search_service,
            search_service,
        ) = await _init_search_service(
            service_config,
            model_settings_store,
            settings,
            None,
            MagicMock(),
            secret_service,
        )

    assert search_service._vector_backend._model_settings_store is model_settings_store
    assert (
        search_service._reranker_backend._model_settings_store is model_settings_store
    )
