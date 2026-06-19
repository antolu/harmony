from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from harmony.api.main import _init_db, _init_search_service  # noqa: PLC2701
from harmony.api.services import PipelineConfig
from harmony.api.services.admin import ModelSettingsStore


@pytest.mark.asyncio
async def test_model_settings_store_constructed_once_before_search_service() -> None:
    """ModelSettingsStore must be on app.state before LLMService/backends are built,
    and the same instance must be shared by all four consumption points."""
    app = FastAPI()

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
        await _init_db(app)

    assert isinstance(app.state.model_settings_store, ModelSettingsStore)
    model_settings_store = app.state.model_settings_store

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
            "harmony.api.main._load_pipeline_config",
            AsyncMock(return_value=PipelineConfig()),
        ),
    ):
        await _init_search_service(app)

    assert app.state.model_settings_store is model_settings_store
    assert app.state.llm_service._model_settings_store is model_settings_store
    assert (
        app.state.search_service._vector_backend._model_settings_store
        is model_settings_store
    )
    assert (
        app.state.search_service._reranker_backend._model_settings_store
        is model_settings_store
    )
