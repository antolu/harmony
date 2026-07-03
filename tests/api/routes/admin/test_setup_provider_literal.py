from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from harmony.api._dependencies import get_model_settings_store, get_service_config_store
from harmony.api.main import app


def _mock_service_config() -> MagicMock:
    store = MagicMock()
    store.validate_elasticsearch = AsyncMock(return_value=(True, "ok"))
    store.validate_redis = AsyncMock(return_value=(True, "ok"))
    store.set = AsyncMock()
    return store


def test_complete_setup_accepts_valid_provider_literal(mock_app_state: None) -> None:
    service_config = _mock_service_config()
    model_settings = MagicMock()
    model_settings.save_embedding_provider = AsyncMock()
    model_settings.save_embedding_model = AsyncMock()
    app.dependency_overrides[get_service_config_store] = lambda: service_config
    app.dependency_overrides[get_model_settings_store] = lambda: model_settings
    try:
        resp = TestClient(app).post(
            "/api/setup/complete",
            json={
                "elasticsearch_url": "http://localhost:9200",
                "redis_url": "redis://localhost:6379",
                "embedding_provider": "ollama",
                "embedding_model": "ollama/qwen3-embedding:0.6b",
            },
        )
    finally:
        app.dependency_overrides.pop(get_service_config_store, None)
        app.dependency_overrides.pop(get_model_settings_store, None)

    assert resp.status_code == 200
    model_settings.save_embedding_provider.assert_awaited_once_with("ollama")


def test_complete_setup_strips_only_provider_prefix_from_model_id(
    mock_app_state: None,
) -> None:
    """A vLLM model id with internal slashes (e.g. a HF org/model path) must keep
    everything after the provider prefix, not just the last path segment."""
    service_config = _mock_service_config()
    model_settings = MagicMock()
    model_settings.save_llm_provider = AsyncMock()
    model_settings.save_llm_model = AsyncMock()
    model_registry_service = MagicMock()
    model_registry_service.create = AsyncMock()
    app.dependency_overrides[get_service_config_store] = lambda: service_config
    app.dependency_overrides[get_model_settings_store] = lambda: model_settings
    app.state.model_registry_service = model_registry_service
    try:
        resp = TestClient(app).post(
            "/api/setup/complete",
            json={
                "elasticsearch_url": "http://localhost:9200",
                "redis_url": "redis://localhost:6379",
                "llm_provider": "hosted_vllm",
                "llm_model": "hosted_vllm/Qwen/Qwen3.5-9B",
            },
        )
    finally:
        app.dependency_overrides.pop(get_service_config_store, None)
        app.dependency_overrides.pop(get_model_settings_store, None)
        del app.state.model_registry_service

    assert resp.status_code == 200
    created_data = model_registry_service.create.call_args.kwargs["data"]
    assert created_data.model_id == "Qwen/Qwen3.5-9B"


def test_complete_setup_rejects_invalid_provider_literal(mock_app_state: None) -> None:
    service_config = _mock_service_config()
    model_settings = MagicMock()
    app.dependency_overrides[get_service_config_store] = lambda: service_config
    app.dependency_overrides[get_model_settings_store] = lambda: model_settings
    try:
        resp = TestClient(app).post(
            "/api/setup/complete",
            json={
                "elasticsearch_url": "http://localhost:9200",
                "redis_url": "redis://localhost:6379",
                "embedding_provider": "not-a-real-provider",
            },
        )
    finally:
        app.dependency_overrides.pop(get_service_config_store, None)
        app.dependency_overrides.pop(get_model_settings_store, None)

    assert resp.status_code == 422
