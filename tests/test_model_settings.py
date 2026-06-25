from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harmony.api.config import Settings
from harmony.api.main import (
    _init_core_services,  # noqa: PLC2701
    _init_search_service,  # noqa: PLC2701
    app,
)
from harmony.api.services import PipelineConfig
from harmony.api.services.admin import ModelSettingsStore


@pytest.mark.asyncio
async def test_model_settings_singleton_identity() -> None:
    """
    D-15: Verify ModelSettingsStore is a true singleton across:
    app.state, LLMService, HarmonyVectorBackend, HarmonyRerankerBackend
    """
    # Create fake objects to avoid running full dependencies
    mock_service_config = AsyncMock()
    app.state.service_config_store = mock_service_config
    app.state.settings = Settings(cors_allowed_origins="http://localhost")

    model_settings_store = ModelSettingsStore()
    app.state.model_settings_store = model_settings_store
    app.state.model_policy_store = MagicMock()
    app.state.db_pool = MagicMock()
    app.state.secret_service = MagicMock()
    app.state.qdrant_service = None
    app.state.model_registry_service = MagicMock()

    mock_pipeline_config = PipelineConfig()

    with (
        patch("harmony.api.main._init_storage_services", return_value=None),
        patch(
            "harmony.api.main.load_pipeline_config", return_value=mock_pipeline_config
        ),
        patch("harmony.api.main.LLMService") as mock_llm,
        patch("harmony.api.main.HarmonyVectorBackend") as mock_vector,
        patch("harmony.api.main.HarmonyRerankerBackend") as mock_reranker,
        patch("harmony.api.main.ExternalSearchService"),
        patch("harmony.api.main.SearchService"),
        patch("harmony.api.main.ConversationService"),
        patch("harmony.api.main.PromptManager"),
    ):
        await _init_core_services(
            app, mock_service_config, model_settings_store, app.state.settings
        )
        await _init_search_service(app)

        # Verify LLMService was constructed
        mock_llm.assert_called_once()

        # Verify VectorBackend got the same instance
        mock_vector.assert_called_once()
        assert (
            mock_vector.call_args.kwargs["model_settings_store"] is model_settings_store
        )

        # Verify RerankerBackend got the same instance
        mock_reranker.assert_called_once()
        assert (
            mock_reranker.call_args.kwargs["model_settings_store"]
            is model_settings_store
        )
