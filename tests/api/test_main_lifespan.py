from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from harmony.api.config import Settings
from harmony.api.main import (
    _init_core_services,  # noqa: PLC2701
    _init_db,  # noqa: PLC2701
    _init_search_service,  # noqa: PLC2701
)
from harmony.services import PipelineConfig
from harmony.services.admin import ModelSettingsStore


@pytest.mark.asyncio
async def test_model_settings_store_constructed_once_before_search_service() -> None:
    """ModelSettingsStore must be on app.state before search backends are built,
    and the same instance must be shared by all consumption points."""
    app = FastAPI()
    settings = Settings(cors_allowed_origins="http://localhost")
    app.state.settings = settings

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
        await _init_db(app, settings)

    assert isinstance(app.state.model_settings_store, ModelSettingsStore)
    model_settings_store = app.state.model_settings_store
    app.state.qdrant_service = None
    app.state.model_registry_service = MagicMock()

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
            app,
            app.state.service_config_store,
            app.state.model_settings_store,
            settings,
        )
        await _init_search_service(app)

    assert app.state.model_settings_store is model_settings_store
    assert (
        app.state.search_service._vector_backend._model_settings_store
        is model_settings_store
    )
    assert (
        app.state.search_service._reranker_backend._model_settings_store
        is model_settings_store
    )
