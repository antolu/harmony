from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from kv_search import SearchHit

from harmony.api.services.search import SearchService


def _make_keyword_backend(hits: list[SearchHit]) -> MagicMock:
    backend = MagicMock()
    backend.keyword_search = AsyncMock(return_value=hits)
    return backend


def _make_vector_backend(hits: list[SearchHit]) -> MagicMock:
    backend = MagicMock()
    backend.vector_search = AsyncMock(return_value=hits)
    return backend


@pytest.mark.asyncio
async def test_returns_vector_hits_when_available() -> None:
    kw_hits = [SearchHit(path="http://a.com/1", score=0.8)]
    vec_hits = [SearchHit(path="http://a.com/1", score=0.95)]
    service = SearchService(
        keyword_backend=_make_keyword_backend(kw_hits),
        vector_backend=_make_vector_backend(vec_hits),
    )
    results = await service.search("test query")
    assert results == vec_hits


@pytest.mark.asyncio
async def test_falls_back_to_keyword_when_vector_empty() -> None:
    kw_hits = [SearchHit(path="http://a.com/1", score=0.8)]
    vec_hits: list[SearchHit] = []
    service = SearchService(
        keyword_backend=_make_keyword_backend(kw_hits),
        vector_backend=_make_vector_backend(vec_hits),
    )
    results = await service.search("test query")
    assert results == kw_hits


@pytest.mark.asyncio
async def test_keyword_search_receives_language() -> None:
    kw_backend = _make_keyword_backend([])
    vec_backend = _make_vector_backend([])
    service = SearchService(keyword_backend=kw_backend, vector_backend=vec_backend)
    await service.search("test", language="fr")
    call_args = kw_backend.keyword_search.call_args[0][0]
    assert call_args.language == "fr"


@pytest.mark.asyncio
async def test_semantic_raises_not_implemented() -> None:
    service = SearchService(
        keyword_backend=_make_keyword_backend([]),
        vector_backend=_make_vector_backend([]),
    )
    with pytest.raises(NotImplementedError):
        await service.search("test", semantic=True)


@pytest.mark.asyncio
async def test_top_k_limits_keyword_results() -> None:
    kw_hits = [SearchHit(path=f"http://a.com/{i}", score=float(i)) for i in range(20)]
    vec_hits: list[SearchHit] = []
    service = SearchService(
        keyword_backend=_make_keyword_backend(kw_hits),
        vector_backend=_make_vector_backend(vec_hits),
    )
    top_k = 5
    results = await service.search("test", top_k=top_k)
    assert len(results) <= top_k
