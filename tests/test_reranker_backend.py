from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kv_search import SearchHit

from harmony.api.backends import HarmonyRerankerBackend


@pytest.mark.asyncio
async def test_rerank_returns_reordered_hits() -> None:
    candidates = [
        SearchHit(path="http://a.com/1", score=0.5, metadata={"content": "doc one"}),
        SearchHit(path="http://a.com/2", score=0.4, metadata={"content": "doc two"}),
        SearchHit(path="http://a.com/3", score=0.3, metadata={"content": "doc three"}),
    ]

    mock_result_0 = MagicMock()
    mock_result_0.index = 2
    mock_result_0.relevance_score = 0.95

    mock_result_1 = MagicMock()
    mock_result_1.index = 0
    mock_result_1.relevance_score = 0.80

    mock_response = MagicMock()
    mock_response.results = [mock_result_0, mock_result_1]

    with (
        patch(
            "harmony.api.backends._reranker.litellm.arerank",
            new=AsyncMock(return_value=mock_response),
        ),
        patch(
            "harmony.api.services.admin._model_settings.model_settings_store.get_reranker_model",
            AsyncMock(return_value="ollama/bge-reranker-v2-m3"),
        ),
    ):
        backend = HarmonyRerankerBackend()
        results = await backend.rerank("test query", candidates, top_n=2)

    assert len(results) == 2
    assert results[0].path == "http://a.com/3"
    assert results[0].score == pytest.approx(0.95)
    assert results[1].path == "http://a.com/1"
    assert results[1].score == pytest.approx(0.80)


@pytest.mark.asyncio
async def test_rerank_uses_content_from_metadata() -> None:
    candidates = [
        SearchHit(
            path="http://a.com/1", score=0.5, metadata={"content": "hello world"}
        ),
    ]

    mock_result = MagicMock()
    mock_result.index = 0
    mock_result.relevance_score = 0.9

    mock_response = MagicMock()
    mock_response.results = [mock_result]

    mock_arerank = AsyncMock(return_value=mock_response)
    with (
        patch("harmony.api.backends._reranker.litellm.arerank", new=mock_arerank),
        patch(
            "harmony.api.services.admin._model_settings.model_settings_store.get_reranker_model",
            AsyncMock(return_value="ollama/bge-reranker-v2-m3"),
        ),
    ):
        backend = HarmonyRerankerBackend()
        await backend.rerank("query", candidates, top_n=1)

    call_kwargs = mock_arerank.call_args.kwargs
    assert call_kwargs["documents"] == ["hello world"]


@pytest.mark.asyncio
async def test_rerank_falls_back_to_path_when_no_content() -> None:
    candidates = [
        SearchHit(path="http://a.com/1", score=0.5, metadata={}),
    ]

    mock_result = MagicMock()
    mock_result.index = 0
    mock_result.relevance_score = 0.9

    mock_response = MagicMock()
    mock_response.results = [mock_result]

    mock_arerank = AsyncMock(return_value=mock_response)
    with (
        patch("harmony.api.backends._reranker.litellm.arerank", new=mock_arerank),
        patch(
            "harmony.api.services.admin._model_settings.model_settings_store.get_reranker_model",
            AsyncMock(return_value="ollama/bge-reranker-v2-m3"),
        ),
    ):
        backend = HarmonyRerankerBackend()
        await backend.rerank("query", candidates, top_n=1)

    call_kwargs = mock_arerank.call_args.kwargs
    assert call_kwargs["documents"] == ["http://a.com/1"]


@pytest.mark.asyncio
async def test_rerank_returns_new_search_hit_instances() -> None:
    original = SearchHit(path="http://a.com/1", score=0.5, metadata={"content": "text"})

    mock_result = MagicMock()
    mock_result.index = 0
    mock_result.relevance_score = 0.99

    mock_response = MagicMock()
    mock_response.results = [mock_result]

    with (
        patch(
            "harmony.api.backends._reranker.litellm.arerank",
            new=AsyncMock(return_value=mock_response),
        ),
        patch(
            "harmony.api.services.admin._model_settings.model_settings_store.get_reranker_model",
            AsyncMock(return_value="ollama/bge-reranker-v2-m3"),
        ),
    ):
        backend = HarmonyRerankerBackend()
        results = await backend.rerank("query", [original], top_n=1)

    assert results[0] is not original
    assert results[0].score == pytest.approx(0.99)
    assert original.score == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_rerank_falls_back_gracefully_on_error() -> None:
    candidates = [
        SearchHit(path="http://a.com/1", score=0.5, metadata={"content": "text"}),
        SearchHit(path="http://a.com/2", score=0.4, metadata={"content": "text2"}),
    ]

    with (
        patch(
            "harmony.api.backends._reranker.litellm.arerank",
            new=AsyncMock(side_effect=Exception("model not found")),
        ),
        patch(
            "harmony.api.services.admin._model_settings.model_settings_store.get_reranker_model",
            AsyncMock(return_value="ollama/bge-reranker-v2-m3"),
        ),
    ):
        backend = HarmonyRerankerBackend()
        results = await backend.rerank("query", candidates, top_n=1)

    assert len(results) == 1
    assert results[0].path == "http://a.com/1"
