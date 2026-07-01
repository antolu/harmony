from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from harmony.scripts.embedder import _load_docs_from_es  # noqa: PLC2701


@pytest.fixture
def mock_es() -> MagicMock:
    mock_es = AsyncMock()
    mock_es.client.search.return_value = {
        "_scroll_id": "dummy_scroll_id",
        "hits": {
            "hits": [
                {
                    "_source": {
                        "url": "http://a.com/1",
                        "title": "Title 1",
                        "content": "Some content",
                    }
                }
            ]
        },
    }
    mock_es.client.scroll.return_value = {"hits": {"hits": []}, "_scroll_id": "abc123"}
    mock_es.client.clear_scroll.return_value = {}
    return mock_es


@pytest.mark.asyncio
async def test_load_docs_from_es_returns_url_and_content(mock_es: MagicMock) -> None:
    docs = await _load_docs_from_es(mock_es, index="harmony-en")
    assert len(docs) == 1
    assert docs[0][0] == "http://a.com/1"
    assert "Some content" in docs[0][1]
