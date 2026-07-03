from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harmony.api._bootstrap import init_core_services, init_search_service
from harmony.api._config import Settings
from harmony.services import PipelineConfig
from harmony.services.admin import ModelSettingsStore


@pytest.mark.asyncio
async def test_model_settings_singleton_identity() -> None:
    """
    D-15: Verify ModelSettingsStore is a true singleton across:
    LLMService, HarmonyVectorBackend, HarmonyRerankerBackend
    """
    # Create fake objects to avoid running full dependencies
    mock_service_config = AsyncMock()
    service_config_defaults = {
        "document_cache_enabled": "false",
        "document_cache_ttl": "3600",
        "document_cache_max_size": "1000",
        "document_cache_backend": "memory",
    }
    mock_service_config.get.side_effect = lambda key: service_config_defaults.get(
        key, ""
    )
    settings = Settings(cors_allowed_origins="http://localhost")

    model_settings_store = ModelSettingsStore()
    model_policy_store = MagicMock()
    mock_pool = MagicMock()
    mock_secret_service = MagicMock()
    mock_model_registry_service = MagicMock()

    mock_pipeline_config = PipelineConfig()

    with (
        patch(
            "harmony.api._bootstrap._search.load_pipeline_config",
            AsyncMock(return_value=mock_pipeline_config),
        ),
        patch("harmony.api._bootstrap._core.LLMService") as mock_llm,
        patch("harmony.api._bootstrap._search.HarmonyVectorBackend") as mock_vector,
        patch("harmony.api._bootstrap._search.HarmonyRerankerBackend") as mock_reranker,
        patch("harmony.api._bootstrap._search.ExternalSearchService"),
        patch("harmony.api._bootstrap._search.SearchService"),
        patch("harmony.api._bootstrap._core.ConversationService"),
        patch("harmony.api._bootstrap._core.PromptManager"),
    ):
        await init_core_services(
            mock_service_config, model_policy_store, mock_pool, settings
        )
        await init_search_service(
            mock_service_config,
            model_settings_store,
            settings,
            None,
            mock_model_registry_service,
            mock_secret_service,
        )

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
