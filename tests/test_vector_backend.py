from __future__ import annotations

import typing
from unittest.mock import AsyncMock, patch

import pytest

from harmony.api.backends.vector import HarmonyVectorBackend


@pytest.fixture
def mock_qdrant() -> AsyncMock:
    service = AsyncMock()
    service.search.return_value = []
    return service


@pytest.fixture
def mock_litellm() -> typing.Generator[AsyncMock, None, None]:
    with patch("harmony.api.backends.vector.litellm") as mock:
        mock.aembedding = AsyncMock(
            return_value=AsyncMock(data=[AsyncMock(embedding=[0.1, 0.2, 0.3])])
        )
        yield mock


@pytest.mark.asyncio
async def test_returns_search_hits(
    mock_qdrant: AsyncMock, mock_litellm: AsyncMock
) -> None:
    mock_qdrant.search.return_value = [("http://a.com/1", 0.9)]
    backend = HarmonyVectorBackend(
        qdrant_service=mock_qdrant, embedding_model="test-model"
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
    backend = HarmonyVectorBackend(
        qdrant_service=mock_qdrant, embedding_model="test-model"
    )
    await backend.vector_search("query", top_n=5, allowlist=["http://a.com/1"])
    call_kwargs = mock_qdrant.search.call_args.kwargs
    assert call_kwargs["allowlist"] == ["http://a.com/1"]


@pytest.mark.asyncio
async def test_calls_litellm_with_model(
    mock_qdrant: AsyncMock, mock_litellm: AsyncMock
) -> None:
    mock_qdrant.search.return_value = []
    backend = HarmonyVectorBackend(
        qdrant_service=mock_qdrant, embedding_model="my-model"
    )
    await backend.vector_search("hello world")
    mock_litellm.aembedding.assert_called_once_with(
        model="my-model", input=["hello world"]
    )


@pytest.mark.asyncio
async def test_empty_on_no_results(
    mock_qdrant: AsyncMock, mock_litellm: AsyncMock
) -> None:
    mock_qdrant.search.return_value = []
    backend = HarmonyVectorBackend(
        qdrant_service=mock_qdrant, embedding_model="test-model"
    )
    hits = await backend.vector_search("query")
    assert hits == []
