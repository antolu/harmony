from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from harmony.tools.embedder import _load_docs_from_es  # noqa: PLC2701


@pytest.fixture
def mock_es() -> MagicMock:
    es = MagicMock()
    es.search.return_value = {
        "hits": {
            "hits": [
                {
                    "_source": {
                        "url": "http://a.com/1",
                        "title": "Test",
                        "content": "Some content",
                    }
                }
            ]
        },
        "_scroll_id": "abc123",
    }
    es.scroll.return_value = {"hits": {"hits": []}, "_scroll_id": "abc123"}
    es.clear_scroll.return_value = {}
    return es


def test_load_docs_from_es_returns_url_and_content(mock_es: MagicMock) -> None:
    docs = _load_docs_from_es(mock_es, index="harmony-en")
    assert len(docs) == 1
    assert docs[0][0] == "http://a.com/1"
    assert "Some content" in docs[0][1]
