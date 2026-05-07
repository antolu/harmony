from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from harmony.api.routes.admin.model_settings import router

app = FastAPI()
app.include_router(router, prefix="/settings/models")
client = TestClient(app)

_DEFAULT_SETTINGS = {
    "embedding_provider": "ollama",
    "embedding_model": "ollama/qwen3-embedding:0.6b",
    "reranker_provider": "ollama",
    "reranker_model": "ollama/bge-reranker-v2-m3",
    "llm_provider": "litellm",
    "llm_model": "gemini/gemini-3-flash-preview",
    "embedding_model_changed_since_last_embed": "false",
}

HTTP_200 = 200


def test_get_model_settings_returns_all_keys() -> None:
    with patch(
        "harmony.api.routes.admin.model_settings.model_settings_store.get_all",
        AsyncMock(return_value=_DEFAULT_SETTINGS),
    ):
        response = client.get("/settings/models")

    assert response.status_code == HTTP_200
    assert response.json()["embedding_model"] == "ollama/qwen3-embedding:0.6b"


def test_patch_model_settings_sets_changed_flag_when_embedding_model_changes() -> None:
    current_settings = dict(_DEFAULT_SETTINGS)

    async def mock_get(key: str) -> str:  # noqa: RUF029
        return current_settings[key]

    async def mock_set(key: str, value: str) -> None:  # noqa: RUF029
        current_settings[key] = value

    async def mock_get_all() -> dict:  # noqa: RUF029
        return current_settings

    with (
        patch(
            "harmony.api.routes.admin.model_settings.model_settings_store"
        ) as mock_store,
        patch("harmony.api.routes.admin.model_settings._validate_model", AsyncMock()),
    ):
        mock_store.get = mock_get
        mock_store.set = mock_set
        mock_store.get_all = mock_get_all
        response = client.patch(
            "/settings/models", json={"embedding_model": "ollama/nomic-embed-text"}
        )

    assert response.status_code == HTTP_200
    assert current_settings["embedding_model_changed_since_last_embed"] == "true"


def test_validate_model_returns_valid_true_for_ollama_pulled_model() -> None:
    with patch("harmony.api.routes.admin.model_settings._validate_model", AsyncMock()):
        response = client.post(
            "/settings/models/validate",
            json={
                "model": "ollama/qwen3-embedding:0.6b",
                "provider": "ollama",
                "model_type": "embedding",
            },
        )

    assert response.status_code == HTTP_200
    assert response.json()["valid"] is True


def test_validate_model_returns_valid_false_on_http_exception() -> None:
    with patch(
        "harmony.api.routes.admin.model_settings._validate_model",
        AsyncMock(side_effect=HTTPException(status_code=400, detail="not found")),
    ):
        response = client.post(
            "/settings/models/validate",
            json={
                "model": "ollama/nonexistent",
                "provider": "ollama",
                "model_type": "embedding",
            },
        )

    assert response.status_code == HTTP_200
    assert response.json()["valid"] is False
    assert "not found" in response.json()["error"]
