from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from harmony.clients._elasticsearch import ElasticsearchService

pytestmark = pytest.mark.asyncio


def _make_service(search_return: dict) -> ElasticsearchService:
    svc = ElasticsearchService.__new__(ElasticsearchService)
    es_config = MagicMock()
    es_config.get_all_indices.return_value = ["harmony-en", "harmony-fr"]
    svc._es_config = es_config  # type: ignore[attr-defined]
    client = MagicMock()
    client.search = AsyncMock(return_value=search_return)
    svc.client = client  # type: ignore[attr-defined]
    return svc


async def test_returns_source_map_keyed_by_id() -> None:
    svc = _make_service({
        "hits": {
            "hits": [
                {"_id": "https://x/a", "_source": {"title": "A", "content": "ca"}},
                {"_id": "https://x/b", "_source": {"title": "B", "content": "cb"}},
            ]
        }
    })
    out = await svc.get_documents_by_ids(["https://x/a", "https://x/b"], ["reader"])
    assert set(out) == {"https://x/a", "https://x/b"}
    assert out["https://x/a"]["title"] == "A"


async def test_applies_acl_and_ids_filter() -> None:
    svc = _make_service({"hits": {"hits": []}})
    await svc.get_documents_by_ids(["u1"], ["reader", "admin"])
    _, kwargs = svc.client.search.call_args  # type: ignore[attr-defined]
    filters = kwargs["query"]["bool"]["filter"]
    assert {"ids": {"values": ["u1"]}} in filters
    assert {"terms": {"acl.allowed_roles": ["reader", "admin"]}} in filters


async def test_empty_ids_skips_query() -> None:
    svc = _make_service({"hits": {"hits": []}})
    assert await svc.get_documents_by_ids([], ["reader"]) == {}
    svc.client.search.assert_not_called()  # type: ignore[attr-defined]


async def test_empty_acl_skips_query() -> None:
    svc = _make_service({"hits": {"hits": []}})
    assert await svc.get_documents_by_ids(["u1"], []) == {}
    svc.client.search.assert_not_called()  # type: ignore[attr-defined]
