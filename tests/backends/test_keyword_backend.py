from __future__ import annotations

import typing
from unittest.mock import AsyncMock, patch

import pytest

from harmony.api.backends import HarmonyKeywordBackend, HarmonyKeywordQueries


@pytest.fixture
def mock_es_client() -> typing.Generator[AsyncMock, None, None]:
    with patch("harmony.api.backends._keyword.elasticsearch.AsyncElasticsearch") as cls:
        client = AsyncMock()
        cls.return_value = client
        yield client


def _make_es_response(hits: list[dict[str, typing.Any]]) -> dict[str, typing.Any]:
    return {
        "hits": {
            "hits": [
                {
                    "_source": {
                        "url": h["url"],
                        "title": h.get("title", ""),
                        "content": h.get("content", ""),
                    },
                    "_score": h.get("score", 1.0),
                }
                for h in hits
            ],
            "total": {"value": len(hits)},
        }
    }


@pytest.mark.asyncio
async def test_routes_to_language_index(mock_es_client: AsyncMock) -> None:
    num_hits = 10
    mock_es_client.search.return_value = _make_es_response([
        {"url": f"http://a.com/{i}"} for i in range(num_hits)
    ])
    backend = HarmonyKeywordBackend(
        host="http://localhost:9200",
        index_base_name="harmony",
        languages=["en", "fr"],
    )
    queries = HarmonyKeywordQueries(queries=["test"], language="en")
    hits = await backend.keyword_search(queries)
    call_kwargs = mock_es_client.search.call_args.kwargs
    assert call_kwargs["index"] == "harmony-en"
    assert mock_es_client.search.call_count == 1
    assert len(hits) == num_hits


@pytest.mark.asyncio
async def test_fallback_to_all_languages_when_none(mock_es_client: AsyncMock) -> None:
    mock_es_client.search.return_value = _make_es_response([])
    languages = ["en", "fr"]
    backend = HarmonyKeywordBackend(
        host="http://localhost:9200",
        index_base_name="harmony",
        languages=languages,
    )
    queries = HarmonyKeywordQueries(queries=["test"], language=None)
    await backend.keyword_search(queries)
    assert mock_es_client.search.call_count == len(languages)


@pytest.mark.asyncio
async def test_deduplicates_hits_across_languages(mock_es_client: AsyncMock) -> None:
    mock_es_client.search.return_value = _make_es_response([{"url": "http://a.com/1"}])
    backend = HarmonyKeywordBackend(
        host="http://localhost:9200",
        index_base_name="harmony",
        languages=["en", "fr"],
    )
    queries = HarmonyKeywordQueries(queries=["test"], language=None)
    hits = await backend.keyword_search(queries)
    assert len(hits) == 1


@pytest.mark.asyncio
async def test_fallback_when_primary_language_below_threshold(
    mock_es_client: AsyncMock,
) -> None:
    primary_hits = 2
    fallback_hits = 3
    languages = ["en", "fr"]
    mock_es_client.search.side_effect = [
        _make_es_response([{"url": f"http://a.com/{i}"} for i in range(primary_hits)]),
        _make_es_response([{"url": f"http://b.com/{i}"} for i in range(fallback_hits)]),
    ]
    backend = HarmonyKeywordBackend(
        host="http://localhost:9200",
        index_base_name="harmony",
        languages=languages,
        min_results_before_fallback=primary_hits + fallback_hits,
    )
    queries = HarmonyKeywordQueries(queries=["test"], language="en")
    hits = await backend.keyword_search(queries)
    assert mock_es_client.search.call_count == len(languages)
    assert len(hits) == primary_hits + fallback_hits
