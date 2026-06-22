from __future__ import annotations

import pytest
from httpx import AsyncClient

from harmony.api.config import Settings
from harmony.clients import ElasticsearchService

settings = Settings()
es_service = ElasticsearchService(host="http://localhost:9200")

pytestmark = pytest.mark.asyncio

HTTP_OK = 200


@pytest.mark.elasticsearch
@pytest.mark.skip(
    reason="Redundant with test_harmony_api_search_endpoint and has event loop issues"
)
async def test_search_endpoint_returns_200(client: AsyncClient) -> None:
    """Search endpoint responds without crashing."""
    # Ensure all language indices exist to avoid 404
    for lang in settings.es_config.languages:
        index_name = settings.es_config.get_index_name(lang)
        if not await es_service.client.indices.exists(index=index_name):
            await es_service.client.indices.create(
                index=index_name, body=settings.es_config.get_index_settings(lang)
            )

    response = await client.get("/search", params={"q": "test"})
    assert response.status_code == HTTP_OK


@pytest.mark.elasticsearch
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


@pytest.mark.elasticsearch
@pytest.mark.skip(
    reason="ES client event loop issue - run API server separately for full testing"
)
async def test_search_with_language_param(client: AsyncClient) -> None:
    """Search with language parameter works."""
    response = await client.get("/search", params={"q": "test", "lang": "en"})
    assert response.status_code == HTTP_OK
    data = response.json()
    assert "total" in data


@pytest.mark.elasticsearch
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


@pytest.mark.elasticsearch
@pytest.mark.skip(
    reason="ES client event loop issue - run API server separately for full testing"
)
async def test_search_with_french_language(client: AsyncClient) -> None:
    """Search with French language preference works."""
    response = await client.get("/search", params={"q": "accès", "lang": "fr"})
    assert response.status_code == HTTP_OK
