from __future__ import annotations

import typing
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harmony.clients import QdrantService


@pytest.fixture
def mock_qdrant_client() -> typing.Generator[AsyncMock, None, None]:
    with patch("harmony.clients._qdrant.qdrant_client") as mock_module:
        client = AsyncMock()
        mock_module.AsyncQdrantClient.return_value = client
        yield client


@pytest.mark.asyncio
async def test_ensure_collection_creates_if_missing(
    mock_qdrant_client: AsyncMock,
) -> None:
    mock_qdrant_client.collection_exists.return_value = False
    service = QdrantService(
        host="http://localhost:6333", collection="test", vector_size=384
    )
    await service.ensure_collection()
    mock_qdrant_client.create_collection.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_collection_skips_if_exists(mock_qdrant_client: AsyncMock) -> None:
    mock_qdrant_client.collection_exists.return_value = True
    service = QdrantService(
        host="http://localhost:6333", collection="test", vector_size=384
    )
    await service.ensure_collection()
    mock_qdrant_client.create_collection.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_vectors(mock_qdrant_client: AsyncMock) -> None:
    service = QdrantService(
        host="http://localhost:6333", collection="test", vector_size=3
    )
    await service.upsert([("http://example.com/a", [0.1, 0.2, 0.3])])
    mock_qdrant_client.upsert.assert_called_once()


@pytest.mark.asyncio
async def test_search_no_allowlist(mock_qdrant_client: AsyncMock) -> None:
    mock_result = MagicMock()
    mock_result.points = []
    mock_qdrant_client.query_points.return_value = mock_result
    service = QdrantService(
        host="http://localhost:6333", collection="test", vector_size=3
    )
    results = await service.search(vector=[0.1, 0.2, 0.3], top_n=5)
    assert results == []
    call_kwargs = mock_qdrant_client.query_points.call_args.kwargs
    assert call_kwargs.get("query_filter") is None


@pytest.mark.asyncio
async def test_search_with_allowlist(mock_qdrant_client: AsyncMock) -> None:
    mock_result = MagicMock()
    mock_result.points = []
    mock_qdrant_client.query_points.return_value = mock_result
    service = QdrantService(
        host="http://localhost:6333", collection="test", vector_size=3
    )
    await service.search(vector=[0.1, 0.2, 0.3], top_n=5, allowlist=["http://a.com"])
    call_kwargs = mock_qdrant_client.query_points.call_args.kwargs
    assert call_kwargs.get("query_filter") is not None


@pytest.mark.asyncio
async def test_is_empty_returns_true_when_no_points(
    mock_qdrant_client: AsyncMock,
) -> None:
    mock_info = MagicMock()
    mock_info.points_count = 0
    mock_qdrant_client.get_collection.return_value = mock_info

    service = QdrantService(
        host="http://localhost:6333", collection="test", vector_size=512
    )
    assert await service.is_empty() is True


@pytest.mark.asyncio
async def test_is_empty_returns_false_when_has_points(
    mock_qdrant_client: AsyncMock,
) -> None:
    mock_info = MagicMock()
    mock_info.points_count = 42
    mock_qdrant_client.get_collection.return_value = mock_info

    service = QdrantService(
        host="http://localhost:6333", collection="test", vector_size=512
    )
    assert await service.is_empty() is False
