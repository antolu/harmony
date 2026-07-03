from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from harmony.agents._source_pool import SourcePool
from harmony.agents.simple import _ai_search as chat
from harmony.models import Source

pytestmark = pytest.mark.asyncio


def test_extract_search_sources_carries_score() -> None:
    payload = json.dumps({
        "results": [{"title": "A", "url": "u", "snippet": "s", "score": 0.8}]
    })
    sources = chat._extract_search_sources(payload)
    assert sources[0].score == pytest.approx(0.8)


def test_extract_search_sources_defaults_score_when_missing() -> None:
    payload = json.dumps({"results": [{"title": "A", "url": "u", "snippet": "s"}]})
    assert chat._extract_search_sources(payload)[0].score == pytest.approx(0.0)


def _pool(*sources: Source) -> SourcePool:
    pool = SourcePool()
    pool.add_all(sources)
    return pool


def test_budgeted_sources_orders_by_score_descending() -> None:
    pool = _pool(
        Source(url="a", snippet="x", score=0.2),
        Source(url="b", snippet="x", score=0.9),
        Source(url="c", snippet="x", score=0.5),
    )
    ordered = [s.url for s in chat._budgeted_sources(pool, token_budget=1000)]
    assert ordered == ["b", "c", "a"]


def test_budgeted_sources_stops_at_token_budget() -> None:
    pool = _pool(
        Source(url="a", snippet="x" * 100, score=0.9),
        Source(url="b", snippet="x" * 100, score=0.5),
    )
    selected = chat._budgeted_sources(pool, token_budget=1)
    assert [s.url for s in selected] == ["a"]


def _make_tool_call(name: str, args: dict[str, object]) -> MagicMock:
    tc = MagicMock()
    tc.id = "call_1"
    tc.function.name = name
    tc.function.arguments = json.dumps(args)
    return tc


def _make_ctx() -> chat.ToolCallContext:
    conv = MagicMock()
    conv.add_tool_call = AsyncMock()
    conv.add_tool_response = AsyncMock()
    return chat.ToolCallContext(
        conversation_id="c1",
        messages=[],
        source_pool=SourcePool(),
        conversation_service=conv,
        sink=chat.StatusSink(),
    )


async def test_process_tool_calls_dedups_by_url_keeping_higher_score() -> None:
    ctx = _make_ctx()
    registry = MagicMock()
    registry.execute = AsyncMock(
        return_value=json.dumps({
            "results": [
                {"title": "A", "url": "https://x.com/a/", "snippet": "a", "score": 0.4},
                {"title": "A2", "url": "https://x.com/a", "snippet": "a", "score": 0.9},
            ]
        })
    )
    await chat._process_tool_calls(
        [_make_tool_call("search_documents", {"query": "q"})], registry, ctx
    )
    ranked = ctx.source_pool.ranked()
    assert len(ranked) == 1
    assert ranked[0].score == pytest.approx(0.9)


async def test_process_tool_calls_recovers_from_tool_failure() -> None:
    ctx = _make_ctx()
    registry = MagicMock()
    registry.execute = AsyncMock(side_effect=RuntimeError("boom"))
    await chat._process_tool_calls(
        [_make_tool_call("search_documents", {"query": "q"})], registry, ctx
    )
    tool_msg = ctx.messages[-1]
    assert tool_msg["role"] == "tool"
    assert "error" in json.loads(str(tool_msg["content"]))
