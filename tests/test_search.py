from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

HTTP_OK = 200


async def test_search_endpoint_returns_200(client: AsyncClient) -> None:
    """Search endpoint responds without crashing."""
    response = await client.get("/search", params={"q": "test"})
    assert response.status_code == HTTP_OK


@pytest.mark.skip(
    reason="ES client event loop issue - run API server separately for full testing"
)
async def test_search_returns_expected_structure(client: AsyncClient) -> None:
    """Search response has expected fields."""
    response = await client.get("/search", params={"q": "access"})
    data = response.json()
    assert "total" in data
    assert "hits" in data
    assert isinstance(data["hits"], list)


@pytest.mark.skip(
    reason="ES client event loop issue - run API server separately for full testing"
)
async def test_search_with_language_param(client: AsyncClient) -> None:
    """Search with language parameter works."""
    response = await client.get("/search", params={"q": "test", "lang": "en"})
    assert response.status_code == HTTP_OK
    data = response.json()
    assert "total" in data


@pytest.mark.skip(
    reason="ES client event loop issue - run API server separately for full testing"
)
async def test_search_returns_hit_structure(client: AsyncClient) -> None:
    """Search results have expected hit structure."""
    response = await client.get("/search", params={"q": "CERN"})
    data = response.json()

    if data["total"] > 0:
        hit = data["hits"][0]
        assert "id" in hit
        assert "title" in hit
        assert "url" in hit
        assert "score" in hit


@pytest.mark.skip(
    reason="ES client event loop issue - run API server separately for full testing"
)
async def test_search_with_french_language(client: AsyncClient) -> None:
    """Search with French language preference works."""
    response = await client.get("/search", params={"q": "accès", "lang": "fr"})
    assert response.status_code == HTTP_OK
