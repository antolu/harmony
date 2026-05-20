from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from harmony.api.dependencies import get_service_config_store
from harmony.api.routes.admin.ollama import router

_mock_service_config = AsyncMock()
_mock_service_config.get = AsyncMock(return_value="http://localhost:11434")

app = FastAPI()
app.dependency_overrides[get_service_config_store] = lambda: _mock_service_config
app.include_router(router, prefix="/models/ollama")
client = TestClient(app)

HTTP_200 = 200
HTTP_502 = 502


def test_list_models_returns_tags() -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "models": [{"name": "qwen3-embedding:0.6b", "size": 100}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("harmony.api.routes.admin.ollama.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get.return_value = mock_response
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        response = client.get("/models/ollama")

    assert response.status_code == HTTP_200
    assert response.json()["models"][0]["name"] == "qwen3-embedding:0.6b"


def test_list_models_returns_502_when_ollama_unreachable() -> None:
    with patch("harmony.api.routes.admin.ollama.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get.side_effect = httpx.ConnectError("refused")
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        response = client.get("/models/ollama")

    assert response.status_code == HTTP_502


def test_delete_model_returns_deleted_true() -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("harmony.api.routes.admin.ollama.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.request.return_value = mock_response
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        response = client.delete("/models/ollama/qwen3-embedding:0.6b")

    assert response.status_code == HTTP_200
    assert response.json() == {"deleted": True}
