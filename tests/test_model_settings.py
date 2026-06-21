from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harmony.api.main import _init_search_service, app  # noqa: PLC2701


@pytest.mark.asyncio
async def test_model_settings_singleton_identity() -> None:
    """
    D-15: Verify ModelSettingsStore is a true singleton across:
    app.state, LLMService, HarmonyVectorBackend, HarmonyRerankerBackend
    """
    # Create fake objects to avoid running full dependencies
    mock_service_config = AsyncMock()
    app.state.service_config_store = mock_service_config

    from harmony.api.services.admin import ModelSettingsStore

    model_settings_store = ModelSettingsStore()
    app.state.model_settings_store = model_settings_store
    app.state.model_policy_store = MagicMock()
    app.state.db_pool = MagicMock()
    app.state.secret_service = MagicMock()

    from harmony.api.services._pipeline_config import PipelineConfig  # noqa: PLC2701

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
    ):
        await _init_search_service(app)

        # Verify LLMService got the same instance
        mock_llm.assert_called_once()
        assert mock_llm.call_args.kwargs["model_settings_store"] is model_settings_store

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
