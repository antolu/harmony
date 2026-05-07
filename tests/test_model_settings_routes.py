from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from harmony.api.routes.admin.model_settings import router
from harmony.api.services.admin.model_settings import ModelSettings

app = FastAPI()
app.include_router(router, prefix="/settings/models")
client = TestClient(app)

HTTP_200 = 200

_DEFAULT_MODEL_SETTINGS = ModelSettings(
    embedding_provider="ollama",
    embedding_model="ollama/qwen3-embedding:0.6b",
    reranker_provider="ollama",
    reranker_model="ollama/bge-reranker-v2-m3",
    llm_provider="litellm",
    llm_model="gemini/gemini-3-flash-preview",
    embedding_model_changed_since_last_embed=False,
)


def test_get_model_settings_returns_all_keys() -> None:
    with patch(
        "harmony.api.routes.admin.model_settings.model_settings_store.get_all",
        AsyncMock(return_value=_DEFAULT_MODEL_SETTINGS),
    ):
        response = client.get("/settings/models")

    assert response.status_code == HTTP_200
    assert response.json()["embedding_model"] == "ollama/qwen3-embedding:0.6b"
    assert response.json()["embedding_model_changed_since_last_embed"] is False


def test_patch_model_settings_sets_changed_flag_when_embedding_model_changes() -> None:
    current = ModelSettings(
        embedding_provider="ollama",
        embedding_model="ollama/qwen3-embedding:0.6b",
        reranker_provider="ollama",
        reranker_model="ollama/bge-reranker-v2-m3",
        llm_provider="litellm",
        llm_model="gemini/gemini-3-flash-preview",
        embedding_model_changed_since_last_embed=False,
    )
    marked: list[bool] = []

    async def mock_get_embedding_provider() -> str:  # noqa: RUF029
        return current.embedding_provider

    async def mock_get_embedding_model() -> str:  # noqa: RUF029
        return current.embedding_model

    async def mock_save_embedding_model(value: str) -> None:  # noqa: RUF029
        current.embedding_model = value

    async def mock_mark_changed() -> None:  # noqa: RUF029
        marked.append(True)
        current.embedding_model_changed_since_last_embed = True

    async def mock_get_all() -> ModelSettings:  # noqa: RUF029
        return current

    with (
        patch(
            "harmony.api.routes.admin.model_settings.model_settings_store"
        ) as mock_store,
        patch("harmony.api.routes.admin.model_settings._validate_model", AsyncMock()),
    ):
        mock_store.get_embedding_provider = mock_get_embedding_provider
        mock_store.get_embedding_model = mock_get_embedding_model
        mock_store.save_embedding_model = mock_save_embedding_model
        mock_store.mark_embedding_changed = mock_mark_changed
        mock_store.get_all = mock_get_all
        response = client.patch(
            "/settings/models", json={"embedding_model": "ollama/nomic-embed-text"}
        )

    assert response.status_code == HTTP_200
    assert marked == [True]


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
