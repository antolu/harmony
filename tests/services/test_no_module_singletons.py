from __future__ import annotations

import inspect

from harmony.clients import _elasticsearch  # noqa: PLC2701
from harmony.services import (
    _conversation,  # noqa: PLC2701
    _document_cache,  # noqa: PLC2701
    _llm,  # noqa: PLC2701
    _search,  # noqa: PLC2701
)


def test_search_module_has_no_global_instance() -> None:
    assert not hasattr(_search, "search_service"), (
        "search_service global must be removed — use app.state"
    )


def test_elasticsearch_module_has_no_global_instance() -> None:
    assert not hasattr(_elasticsearch, "es_service"), (
        "es_service global must be removed — use app.state"
    )


def test_llm_module_has_no_global_instance() -> None:
    assert not hasattr(_llm, "llm_service"), (
        "llm_service global must be removed — use app.state"
    )


def test_document_cache_module_has_no_global_instance() -> None:
    assert not hasattr(_document_cache, "document_cache"), (
        "document_cache global must be removed — use app.state"
    )


def test_conversation_module_has_no_global_instance() -> None:
    assert not hasattr(_conversation, "conversation_service"), (
        "conversation_service global must be removed — use app.state"
    )


def test_agentic_search_route_has_no_orchestrator_global() -> None:
    from harmony.api.routes import agentic_search

    assert not hasattr(agentic_search, "_orchestrator"), (
        "_orchestrator global must be removed — use app.state"
    )


def test_document_cache_accepts_constructor_args() -> None:
    from harmony.services import DocumentCache

    cache = DocumentCache(ttl=60, max_size=10)
    assert cache.ttl == 60
    assert cache.max_size == 10


def test_llm_init_does_not_mutate_environ() -> None:
    source = inspect.getsource(_llm.LLMService.__init__)
    assert "os.environ" not in source, (
        "LLMService.__init__ must not mutate os.environ — do it in lifespan"
    )
