from __future__ import annotations

import json
import typing

import pytest

from harmony.api.tools._documents import FetchURLTool  # noqa: PLC2701


class _StubSink:
    def emit(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        return None


class _StubES:
    def __init__(self, doc: dict[str, typing.Any] | Exception) -> None:
        self._doc = doc
        self.calls: list[str] = []

    async def get_document(self, doc_id: str, **_: typing.Any) -> dict[str, typing.Any]:
        self.calls.append(doc_id)
        if isinstance(self._doc, Exception):
            raise self._doc
        return self._doc


@pytest.mark.asyncio
async def test_serves_indexed_document_without_network() -> None:
    es = _StubES({"title": "Indexed", "content": "full body text"})
    tool = FetchURLTool(document_cache=None, es_service=es)  # type: ignore[arg-type]

    out = await tool.execute(_StubSink(), url="https://x.test/doc")
    parsed = json.loads(out)

    assert parsed["source"] == "elasticsearch"
    assert parsed["content"] == "full body text"
    assert parsed["title"] == "Indexed"
    assert es.calls == ["https://x.test/doc"]


@pytest.mark.asyncio
async def test_missing_in_es_returns_none_to_fall_through() -> None:
    es = _StubES(KeyError("not found"))
    tool = FetchURLTool(document_cache=None, es_service=es)  # type: ignore[arg-type]

    assert await tool._try_elasticsearch("https://x.test/doc") is None


@pytest.mark.asyncio
async def test_empty_content_falls_through() -> None:
    es = _StubES({"title": "Indexed", "content": ""})
    tool = FetchURLTool(document_cache=None, es_service=es)  # type: ignore[arg-type]

    assert await tool._try_elasticsearch("https://x.test/doc") is None


@pytest.mark.asyncio
async def test_no_es_service_falls_through() -> None:
    tool = FetchURLTool(document_cache=None, es_service=None)  # type: ignore[arg-type]

    assert await tool._try_elasticsearch("https://x.test/doc") is None
