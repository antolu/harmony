from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from harmony.api.services.admin import ServiceConfigStore


@pytest.fixture
def store() -> ServiceConfigStore:
    return ServiceConfigStore()


@pytest.mark.asyncio
async def test_validate_ollama_reports_model_count(store: ServiceConfigStore) -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"models": [{"name": "qwen3:8b"}]}

    with patch(
        "harmony.api.services.admin._service_config.httpx.AsyncClient"
    ) as mock_cls:
        mock_http = AsyncMock()
        mock_http.get.return_value = mock_response
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        ok, message = await store.validate_ollama("http://localhost:11434")

    assert ok is True
    assert "1 model available" in message


@pytest.mark.asyncio
async def test_validate_ollama_pluralizes_model_count(
    store: ServiceConfigStore,
) -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"models": [{"name": "a"}, {"name": "b"}]}

    with patch(
        "harmony.api.services.admin._service_config.httpx.AsyncClient"
    ) as mock_cls:
        mock_http = AsyncMock()
        mock_http.get.return_value = mock_response
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        ok, message = await store.validate_ollama("http://localhost:11434")

    assert ok is True
    assert "2 models available" in message


@pytest.mark.asyncio
async def test_validate_ollama_returns_false_on_connection_error(
    store: ServiceConfigStore,
) -> None:
    with patch(
        "harmony.api.services.admin._service_config.httpx.AsyncClient"
    ) as mock_cls:
        mock_http = AsyncMock()
        mock_http.get.side_effect = httpx.ConnectError("refused")
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        ok, message = await store.validate_ollama("http://localhost:11434")

    assert ok is False
    assert "Connection failed" in message


@pytest.mark.asyncio
async def test_validate_vllm_returns_true_on_healthy_response(
    store: ServiceConfigStore,
) -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch(
        "harmony.api.services.admin._service_config.httpx.AsyncClient"
    ) as mock_cls:
        mock_http = AsyncMock()
        mock_http.get.return_value = mock_response
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        ok, message = await store.validate_vllm("http://localhost:8000")

    assert ok is True
    assert message == "Connected successfully"


@pytest.mark.asyncio
async def test_validate_vllm_returns_false_when_unreachable(
    store: ServiceConfigStore,
) -> None:
    with patch(
        "harmony.api.services.admin._service_config.httpx.AsyncClient"
    ) as mock_cls:
        mock_http = AsyncMock()
        mock_http.get.side_effect = httpx.ConnectError("refused")
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        ok, message = await store.validate_vllm("http://localhost:8000")

    assert ok is False
    assert "Connection failed" in message
