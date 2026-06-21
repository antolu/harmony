from __future__ import annotations

import inspect
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient

from harmony.api.routes.search import search

HTTP_OK = 200


def test_search_signature_has_at_most_five_params() -> None:
    params = inspect.signature(search).parameters
    assert len(params) <= 6


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_app_state")
async def test_search_endpoint_returns_expected_shape(client: AsyncClient) -> None:
    hit = MagicMock()
    hit.score = 0.9
    hit.path = "https://example.com/foo"
    hit.metadata = {
        "title": "Foo",
        "language": "en",
        "domain": "example.com",
        "content": "some content",
        "source_type": "internal",
        "provider": "",
    }
    from harmony.api.main import app

    app.state.search_service.search.return_value = [hit]

    response = await client.get(
        "/api/search",
        params={"q": "foo", "lang": "en", "use_external_search": "true"},
    )
    assert response.status_code == HTTP_OK
    data = response.json()
    assert data["total"] == 1
    assert data["hits"][0]["url"] == "https://example.com/foo"
    assert data["hits"][0]["title"] == "Foo"
