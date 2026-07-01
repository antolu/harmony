from __future__ import annotations

from unittest import mock

import pytest
from kv_search import SearchHit

from harmony.services._pipeline_config import PipelineConfig
from harmony.services._search import SearchContext, SearchService


def _service(
    *, keyword_hits: list[SearchHit], vector_hits: list[SearchHit]
) -> tuple[SearchService, mock.AsyncMock, mock.AsyncMock]:
    keyword_backend = mock.AsyncMock()
    keyword_backend.keyword_search.return_value = keyword_hits
    vector_backend = mock.AsyncMock()
    vector_backend.vector_search.return_value = vector_hits
    config = PipelineConfig()
    service = SearchService(
        keyword_backend=keyword_backend,
        vector_backend=vector_backend,
        reranker_backend=None,
        config=config,
    )
    return service, keyword_backend, vector_backend


@pytest.mark.asyncio
async def test_all_keyword_variants_passed_to_backend() -> None:
    service, kw, _ = _service(
        keyword_hits=[SearchHit(path=f"/d{i}", score=1.0) for i in range(5)],
        vector_hits=[SearchHit(path="/d0", score=0.9)],
    )
    await service.search(
        SearchContext(
            query="q",
            primary_query="semantic sentence",
            keyword_variants=["kw a", "kw b", "kw c"],
            top_k=50,
        )
    )
    passed = kw.keyword_search.call_args.args[0]
    assert passed.queries == ["kw a", "kw b", "kw c"]


@pytest.mark.asyncio
async def test_single_vector_search_uses_primary_query() -> None:
    service, _, vec = _service(
        keyword_hits=[SearchHit(path=f"/d{i}", score=1.0) for i in range(5)],
        vector_hits=[SearchHit(path="/d0", score=0.9)],
    )
    await service.search(
        SearchContext(
            query="q",
            primary_query="semantic sentence",
            keyword_variants=["kw a"],
            top_k=50,
        )
    )
    assert vec.vector_search.call_count == 1
    assert vec.vector_search.call_args.args[0] == "semantic sentence"


@pytest.mark.asyncio
async def test_agentic_path_returns_more_than_ten_without_reranker() -> None:
    # Blocker regression guard (D-05/D-15): with reranking off and >10 vector
    # candidates, the agentic caller (large top_k) must not be capped at 10.
    vector_hits = [SearchHit(path=f"/d{i}", score=1.0 - i / 100) for i in range(40)]
    service, _, _ = _service(
        keyword_hits=[SearchHit(path=f"/d{i}", score=1.0) for i in range(40)],
        vector_hits=vector_hits,
    )
    result = await service.search(
        SearchContext(
            query="q",
            primary_query="semantic",
            keyword_variants=["kw"],
            top_k=50,
        )
    )
    assert len(result) > 10


@pytest.mark.asyncio
async def test_back_compat_single_query_defaults() -> None:
    service, kw, vec = _service(
        keyword_hits=[SearchHit(path="/d0", score=1.0)],
        vector_hits=[SearchHit(path="/d0", score=0.9)],
    )
    await service.search(SearchContext(query="only query", top_k=5))
    assert kw.keyword_search.call_args.args[0].queries == ["only query"]
    assert vec.vector_search.call_args.args[0] == "only query"


def test_pipeline_config_widened_defaults() -> None:
    config = PipelineConfig()
    assert config.keyword_candidates_n == 150
    assert config.vector_top_k == 50
