from __future__ import annotations

import dataclasses
from unittest.mock import AsyncMock, MagicMock

import pytest
from kv_search import SearchHit

from harmony.authz import AuthorizationContext
from harmony.services import PipelineConfig, SearchContext, SearchService


def _make_keyword_backend(hits: list[SearchHit]) -> MagicMock:
    backend = MagicMock()
    backend.keyword_search = AsyncMock(return_value=hits)
    return backend


def _make_vector_backend(hits: list[SearchHit]) -> MagicMock:
    backend = MagicMock()
    backend.vector_search = AsyncMock(return_value=hits)
    return backend


def _make_reranker_backend(hits: list[SearchHit]) -> MagicMock:
    backend = MagicMock()
    backend.rerank = AsyncMock(return_value=hits)
    return backend


def _make_service(
    kw_hits: list[SearchHit],
    vec_hits: list[SearchHit],
    config: PipelineConfig | None = None,
) -> SearchService:
    return SearchService(
        keyword_backend=_make_keyword_backend(kw_hits),
        vector_backend=_make_vector_backend(vec_hits),
        config=config or PipelineConfig(),
    )


def _make_authz_context(roles: list[str]) -> AuthorizationContext:
    return AuthorizationContext(
        user_id="user-1",
        harmony_roles=roles,
        harmony_groups=[],
        raw_claims={},
        trace_id="trace-1",
        auth_mode="jwt",
    )


@pytest.mark.asyncio
async def test_returns_vector_hits_when_available() -> None:
    kw_hits = [SearchHit(path="http://a.com/1", score=0.8)]
    vec_hits = [SearchHit(path="http://a.com/1", score=0.95)]
    service = _make_service(kw_hits, vec_hits)
    ctx = _make_authz_context(["reader"])
    results = await service.search(SearchContext(query="test query", authz_context=ctx))
    assert results == vec_hits


@pytest.mark.asyncio
async def test_falls_back_to_keyword_when_vector_empty() -> None:
    config = PipelineConfig(search_top_k=10)
    kw_hits = [SearchHit(path="http://a.com/1", score=0.8)]
    vec_hits: list[SearchHit] = []
    service = _make_service(kw_hits, vec_hits, config=config)
    ctx = _make_authz_context(["reader"])
    results = await service.search(SearchContext(query="test query", authz_context=ctx))
    assert results == kw_hits


@pytest.mark.asyncio
async def test_keyword_search_receives_language() -> None:
    kw_backend = _make_keyword_backend([])
    vec_backend = _make_vector_backend([])
    service = SearchService(
        keyword_backend=kw_backend,
        vector_backend=vec_backend,
        config=PipelineConfig(),
    )
    ctx = _make_authz_context(["reader"])
    await service.search(SearchContext(query="test", language="fr", authz_context=ctx))
    call_args = kw_backend.keyword_search.call_args[0][0]
    assert call_args.language == "fr"


@pytest.mark.asyncio
async def test_vector_stage_skipped_when_disabled() -> None:
    config = PipelineConfig(vector_search_enabled=False, search_top_k=10)
    kw_hits = [SearchHit(path="http://a.com/1", score=0.8)]
    vec_backend = _make_vector_backend([SearchHit(path="http://a.com/2", score=0.99)])
    service = SearchService(
        keyword_backend=_make_keyword_backend(kw_hits),
        vector_backend=vec_backend,
        config=config,
    )
    ctx = _make_authz_context(["reader"])
    results = await service.search(SearchContext(query="test", authz_context=ctx))
    vec_backend.vector_search.assert_not_called()
    assert results == kw_hits


@pytest.mark.asyncio
async def test_reranker_stage_called_when_enabled() -> None:
    reranked = [SearchHit(path="http://a.com/1", score=0.99)]
    reranker = _make_reranker_backend(reranked)
    config = PipelineConfig(reranker_enabled=True)
    kw_hits = [SearchHit(path="http://a.com/1", score=0.8)]
    vec_hits = [SearchHit(path="http://a.com/1", score=0.9)]
    service = SearchService(
        keyword_backend=_make_keyword_backend(kw_hits),
        vector_backend=_make_vector_backend(vec_hits),
        reranker_backend=reranker,
        config=config,
    )
    ctx = _make_authz_context(["reader"])
    results = await service.search(SearchContext(query="test", authz_context=ctx))
    reranker.rerank.assert_called_once()
    assert results == reranked


@pytest.mark.asyncio
async def test_reranker_stage_skipped_when_disabled() -> None:
    reranker = _make_reranker_backend([])
    config = PipelineConfig(reranker_enabled=False)
    kw_hits = [SearchHit(path="http://a.com/1", score=0.8)]
    vec_hits = [SearchHit(path="http://a.com/1", score=0.9)]
    service = SearchService(
        keyword_backend=_make_keyword_backend(kw_hits),
        vector_backend=_make_vector_backend(vec_hits),
        reranker_backend=reranker,
        config=config,
    )
    ctx = _make_authz_context(["reader"])
    await service.search(SearchContext(query="test", authz_context=ctx))
    reranker.rerank.assert_not_called()


@pytest.mark.asyncio
async def test_search_top_k_limits_results() -> None:
    config = PipelineConfig(vector_search_enabled=False, search_top_k=3)
    kw_hits = [SearchHit(path=f"http://a.com/{i}", score=float(i)) for i in range(10)]
    service = SearchService(
        keyword_backend=_make_keyword_backend(kw_hits),
        vector_backend=_make_vector_backend([]),
        config=config,
    )
    ctx = _make_authz_context(["reader"])
    results = await service.search(SearchContext(query="test", authz_context=ctx))
    assert len(results) <= 3


@pytest.mark.asyncio
async def test_pipeline_config_runtime_toggle() -> None:
    config = PipelineConfig(reranker_enabled=False)
    reranker = _make_reranker_backend([SearchHit(path="http://a.com/1", score=0.99)])
    kw_hits = [SearchHit(path="http://a.com/1", score=0.8)]
    vec_hits = [SearchHit(path="http://a.com/1", score=0.9)]
    service = SearchService(
        keyword_backend=_make_keyword_backend(kw_hits),
        vector_backend=_make_vector_backend(vec_hits),
        reranker_backend=reranker,
        config=config,
    )
    ctx = _make_authz_context(["reader"])
    await service.search(SearchContext(query="test", authz_context=ctx))
    reranker.rerank.assert_not_called()

    service.config = dataclasses.replace(config, reranker_enabled=True)
    await service.search(SearchContext(query="test", authz_context=ctx))
    reranker.rerank.assert_called_once()


@pytest.mark.asyncio
async def test_search_service_passes_user_roles_to_keyword_backend() -> None:
    kw_backend = _make_keyword_backend([])
    vec_backend = _make_vector_backend([])
    service = SearchService(
        keyword_backend=kw_backend,
        vector_backend=vec_backend,
        config=PipelineConfig(),
    )
    ctx = _make_authz_context(["admin", "read_only"])
    await service.search(SearchContext(query="test", authz_context=ctx))
    call_args = kw_backend.keyword_search.call_args[0][0]
    assert call_args.acl_terms == ["admin", "read_only"]


@pytest.mark.asyncio
async def test_search_service_with_no_authz_context_uses_empty_acl() -> None:
    kw_backend = _make_keyword_backend([])
    vec_backend = _make_vector_backend([])
    service = SearchService(
        keyword_backend=kw_backend,
        vector_backend=vec_backend,
        config=PipelineConfig(),
    )
    await service.search(SearchContext(query="test", authz_context=None))
    call_args = kw_backend.keyword_search.call_args[0][0]
    assert call_args.acl_terms == []


@pytest.mark.asyncio
async def test_vector_search_receives_acl_filtered_allowlist_only() -> None:
    kw_hits = [
        SearchHit(path="http://a.com/1", score=0.9),
        SearchHit(path="http://a.com/2", score=0.8),
    ]
    vec_backend = _make_vector_backend([])
    config = PipelineConfig(vector_search_enabled=True, keyword_candidates_n=10)
    service = SearchService(
        keyword_backend=_make_keyword_backend(kw_hits),
        vector_backend=vec_backend,
        config=config,
    )
    ctx = _make_authz_context(["reader"])
    await service.search(SearchContext(query="test", authz_context=ctx))
    call_kwargs = vec_backend.vector_search.call_args.kwargs
    assert set(call_kwargs["allowlist"]) == {"http://a.com/1", "http://a.com/2"}
