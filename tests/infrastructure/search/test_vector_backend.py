from __future__ import annotations

import typing
from unittest.mock import AsyncMock, patch

import pytest

from harmony.infrastructure.search import HarmonyVectorBackend


@pytest.fixture
def mock_qdrant() -> AsyncMock:
    service = AsyncMock()
    service.search.return_value = []
    return service


@pytest.fixture
def mock_litellm() -> typing.Generator[AsyncMock, None, None]:
    with patch("harmony.infrastructure.search._vector.litellm") as mock:
        mock.aembedding = AsyncMock(
            return_value=AsyncMock(data=[AsyncMock(embedding=[0.1, 0.2, 0.3])])
        )
        yield mock


@pytest.mark.asyncio
async def test_returns_search_hits(
    mock_qdrant: AsyncMock, mock_litellm: AsyncMock
) -> None:
    mock_qdrant.search.return_value = [("http://a.com/1", 0.9)]
    mock_config = AsyncMock()
    mock_config.get = AsyncMock(return_value="false")
    mock_model_settings = AsyncMock()
    mock_model_settings.get_embedding_model = AsyncMock(return_value="test-model")
    backend = HarmonyVectorBackend(
        qdrant_service=mock_qdrant,
        service_config=mock_config,
        model_settings_store=mock_model_settings,
    )
    hits = await backend.vector_search("test query", top_n=5)
    assert len(hits) == 1
    assert hits[0].path == "http://a.com/1"
    assert hits[0].score == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_passes_allowlist_to_qdrant(
    mock_qdrant: AsyncMock, mock_litellm: AsyncMock
) -> None:
    mock_qdrant.search.return_value = []
    mock_config = AsyncMock()
    mock_config.get = AsyncMock(return_value="false")
    mock_model_settings = AsyncMock()
    mock_model_settings.get_embedding_model = AsyncMock(return_value="test-model")
    backend = HarmonyVectorBackend(
        qdrant_service=mock_qdrant,
        service_config=mock_config,
        model_settings_store=mock_model_settings,
    )
    await backend.vector_search("query", top_n=5, allowlist=["http://a.com/1"])
    call_kwargs = mock_qdrant.search.call_args.kwargs
    assert call_kwargs["allowlist"] == ["http://a.com/1"]


@pytest.mark.asyncio
async def test_calls_litellm_with_model(
    mock_qdrant: AsyncMock, mock_litellm: AsyncMock
) -> None:
    mock_qdrant.search.return_value = []
    mock_config = AsyncMock()
    mock_config.get = AsyncMock(return_value="false")
    mock_model_settings = AsyncMock()
    mock_model_settings.get_embedding_model = AsyncMock(return_value="my-model")
    backend = HarmonyVectorBackend(
        qdrant_service=mock_qdrant,
        service_config=mock_config,
        model_settings_store=mock_model_settings,
    )
    await backend.vector_search("hello world")
    call_kwargs = mock_litellm.aembedding.call_args.kwargs
    assert call_kwargs["model"] == "my-model"
    assert call_kwargs["input"] == ["hello world"]
    assert call_kwargs["metadata"]["agent_step"] == "embedding"


@pytest.mark.asyncio
async def test_empty_on_no_results(
    mock_qdrant: AsyncMock, mock_litellm: AsyncMock
) -> None:
    mock_qdrant.search.return_value = []
    mock_config = AsyncMock()
    mock_config.get = AsyncMock(return_value="false")
    mock_model_settings = AsyncMock()
    mock_model_settings.get_embedding_model = AsyncMock(return_value="test-model")
    backend = HarmonyVectorBackend(
        qdrant_service=mock_qdrant,
        service_config=mock_config,
        model_settings_store=mock_model_settings,
    )
    hits = await backend.vector_search("query")
    assert hits == []
