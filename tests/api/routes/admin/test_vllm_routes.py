from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from harmony.api._dependencies import get_current_user
from harmony.api.routes.admin._vllm import router
from harmony.models import UserIdentity

HTTP_200 = 200
HTTP_502 = 502


@pytest.fixture
def client(admin_user: UserIdentity) -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.include_router(router, prefix="/models/vllm")
    return TestClient(app)


def test_list_vllm_models_returns_model_names(client: TestClient) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [{"id": "Qwen/Qwen3.5-9B"}, {"id": "meta-llama/Llama-3-8B"}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("harmony.api.routes.admin._vllm.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get.return_value = mock_response
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        response = client.get("/models/vllm?host=http://localhost:8000")

    assert response.status_code == HTTP_200
    assert response.json() == {
        "models": [{"name": "Qwen/Qwen3.5-9B"}, {"name": "meta-llama/Llama-3-8B"}]
    }


def test_list_vllm_models_returns_empty_list_when_no_data_key(
    client: TestClient,
) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {}
    mock_response.raise_for_status = MagicMock()

    with patch("harmony.api.routes.admin._vllm.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get.return_value = mock_response
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        response = client.get("/models/vllm?host=http://localhost:8000")

    assert response.status_code == HTTP_200
    assert response.json() == {"models": []}


def test_list_vllm_models_returns_502_when_host_unreachable(
    client: TestClient,
) -> None:
    with patch("harmony.api.routes.admin._vllm.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get.side_effect = httpx.ConnectError("refused")
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        response = client.get("/models/vllm?host=http://localhost:8000")

    assert response.status_code == HTTP_502
    assert "vLLM unreachable" in response.json()["detail"]


def test_list_vllm_models_returns_502_on_http_status_error(
    client: TestClient,
) -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 error", request=MagicMock(), response=MagicMock(status_code=500)
    )

    with patch("harmony.api.routes.admin._vllm.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get.return_value = mock_response
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        response = client.get("/models/vllm?host=http://localhost:8000")

    assert response.status_code == HTTP_502


def test_list_vllm_models_requires_host_query_param(client: TestClient) -> None:
    response = client.get("/models/vllm")
    assert response.status_code == 422
