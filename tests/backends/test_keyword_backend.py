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


def _make_count_response(count: int) -> dict[str, typing.Any]:
    return {"count": count}


@pytest.mark.asyncio
async def test_routes_to_language_index(mock_es_client: AsyncMock) -> None:
    num_hits = 10
    mock_es_client.search.return_value = _make_es_response([
        {"url": f"http://a.com/{i}"} for i in range(num_hits)
    ])
    mock_es_client.count.return_value = _make_count_response(0)
    backend = HarmonyKeywordBackend(
        host="http://localhost:9200",
        index_base_name="harmony",
        languages=["en", "fr"],
    )
    queries = HarmonyKeywordQueries(
        queries=["test"], language="en", acl_terms=["reader"]
    )
    hits = await backend.keyword_search(queries)
    search_calls = list(mock_es_client.search.call_args_list)
    assert search_calls[0].kwargs["index"] == "harmony-en"
    assert mock_es_client.search.call_count == 1
    assert len(hits) == num_hits


@pytest.mark.asyncio
async def test_fallback_to_all_languages_when_none(mock_es_client: AsyncMock) -> None:
    mock_es_client.search.return_value = _make_es_response([])
    mock_es_client.count.return_value = _make_count_response(0)
    languages = ["en", "fr"]
    backend = HarmonyKeywordBackend(
        host="http://localhost:9200",
        index_base_name="harmony",
        languages=languages,
    )
    queries = HarmonyKeywordQueries(
        queries=["test"], language=None, acl_terms=["reader"]
    )
    await backend.keyword_search(queries)
    assert mock_es_client.search.call_count == len(languages)


@pytest.mark.asyncio
async def test_deduplicates_hits_across_languages(mock_es_client: AsyncMock) -> None:
    mock_es_client.search.return_value = _make_es_response([{"url": "http://a.com/1"}])
    mock_es_client.count.return_value = _make_count_response(0)
    backend = HarmonyKeywordBackend(
        host="http://localhost:9200",
        index_base_name="harmony",
        languages=["en", "fr"],
    )
    queries = HarmonyKeywordQueries(
        queries=["test"], language=None, acl_terms=["reader"]
    )
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
    mock_es_client.count.return_value = _make_count_response(0)
    backend = HarmonyKeywordBackend(
        host="http://localhost:9200",
        index_base_name="harmony",
        languages=languages,
        min_results_before_fallback=primary_hits + fallback_hits,
    )
    queries = HarmonyKeywordQueries(
        queries=["test"], language="en", acl_terms=["reader"]
    )
    hits = await backend.keyword_search(queries)
    assert mock_es_client.search.call_count == len(languages)
    assert len(hits) == primary_hits + fallback_hits


@pytest.mark.asyncio
async def test_acl_filter_included_in_es_query(mock_es_client: AsyncMock) -> None:
    mock_es_client.search.return_value = _make_es_response([])
    mock_es_client.count.return_value = _make_count_response(0)
    backend = HarmonyKeywordBackend(
        host="http://localhost:9200",
        index_base_name="harmony",
        languages=["en"],
    )
    queries = HarmonyKeywordQueries(
        queries=["test"], language="en", acl_terms=["admin", "read_only"]
    )
    await backend.keyword_search(queries)
    call_kwargs = mock_es_client.search.call_args.kwargs
    query = call_kwargs["query"]
    assert "bool" in query
    assert "filter" in query["bool"]
    filters = query["bool"]["filter"]
    terms_filter = next(f for f in filters if "terms" in f)
    exists_filter = next(f for f in filters if "exists" in f)
    assert terms_filter["terms"]["acl.allowed_roles"] == ["admin", "read_only"]
    assert exists_filter["exists"]["field"] == "acl.policy_version"


@pytest.mark.asyncio
async def test_empty_acl_terms_returns_empty(mock_es_client: AsyncMock) -> None:
    backend = HarmonyKeywordBackend(
        host="http://localhost:9200",
        index_base_name="harmony",
        languages=["en"],
    )
    queries = HarmonyKeywordQueries(queries=["test"], language="en", acl_terms=[])
    hits = await backend.keyword_search(queries)
    assert hits == []
    mock_es_client.search.assert_not_called()


@pytest.mark.asyncio
async def test_missing_acl_docs_logged_as_security_event(
    mock_es_client: AsyncMock,
) -> None:
    mock_es_client.search.return_value = _make_es_response([{"url": "http://a.com/1"}])
    mock_es_client.count.return_value = _make_count_response(5)
    backend = HarmonyKeywordBackend(
        host="http://localhost:9200",
        index_base_name="harmony",
        languages=["en"],
    )
    queries = HarmonyKeywordQueries(
        queries=["test"], language="en", acl_terms=["reader"]
    )
    with patch("harmony.api.backends._keyword.structlog") as mock_structlog:
        mock_logger = mock_structlog.get_logger.return_value
        await backend.keyword_search(queries)
    mock_logger.warning.assert_called_once()
    call_kwargs = mock_logger.warning.call_args
    assert call_kwargs[0][0] == "acl_missing_docs_detected"
    assert call_kwargs[1]["count"] == 5
