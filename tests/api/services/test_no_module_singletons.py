from __future__ import annotations

import inspect


def test_search_module_has_no_global_instance() -> None:
    from harmony.api.services import search

    assert not hasattr(search, "search_service"), (
        "search_service global must be removed — use app.state"
    )


def test_elasticsearch_module_has_no_global_instance() -> None:
    from harmony.api.services import elasticsearch

    assert not hasattr(elasticsearch, "es_service"), (
        "es_service global must be removed — use app.state"
    )


def test_llm_module_has_no_global_instance() -> None:
    from harmony.api.services import llm

    assert not hasattr(llm, "llm_service"), (
        "llm_service global must be removed — use app.state"
    )


def test_document_cache_module_has_no_global_instance() -> None:
    from harmony.api.services import document_cache as dc_mod

    assert not hasattr(dc_mod, "document_cache"), (
        "document_cache global must be removed — use app.state"
    )


def test_conversation_module_has_no_global_instance() -> None:
    from harmony.api.services import conversation

    assert not hasattr(conversation, "conversation_service"), (
        "conversation_service global must be removed — use app.state"
    )


def test_agentic_search_route_has_no_orchestrator_global() -> None:
    from harmony.api.routes import agentic_search

    assert not hasattr(agentic_search, "_orchestrator"), (
        "_orchestrator global must be removed — use app.state"
    )


def test_document_cache_accepts_constructor_args() -> None:
    from harmony.api.services.document_cache import DocumentCache

    cache = DocumentCache(ttl=60, max_size=10)
    assert cache.ttl == 60
    assert cache.max_size == 10


def test_llm_init_does_not_mutate_environ() -> None:
    from harmony.api.services import llm

    source = inspect.getsource(llm.LLMService.__init__)
    assert "os.environ" not in source, (
        "LLMService.__init__ must not mutate os.environ — do it in lifespan"
    )
