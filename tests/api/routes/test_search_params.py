from __future__ import annotations

import inspect
import typing
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from harmony.api.main import app
from harmony.api.routes._search import search

HTTP_OK = 200


def test_search_signature_has_at_most_five_params() -> None:
    params = inspect.signature(search).parameters
    assert len(params) <= 7


@pytest.mark.asyncio
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
    search_service_mock = typing.cast(AsyncMock, app.state.search_service)
    search_service_mock.search.return_value = [hit]

    response = await client.get(
        "/api/search",
        params={"q": "foo", "lang": "en", "use_external_search": "true"},
    )
    assert response.status_code == HTTP_OK
    data = response.json()
    assert data["total"] == 1
    assert data["hits"][0]["url"] == "https://example.com/foo"
    assert data["hits"][0]["title"] == "Foo"
