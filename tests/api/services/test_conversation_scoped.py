from __future__ import annotations

import inspect

from harmony.api.services import ConversationService


def test_create_has_mode_param() -> None:
    sig = inspect.signature(ConversationService.create)
    assert "mode" in sig.parameters, "create() must have mode parameter"
    assert sig.parameters["mode"].default == "search", "mode must default to 'search'"


def test_add_message_scoped_exists() -> None:
    assert hasattr(ConversationService, "add_message_scoped"), (
        "add_message_scoped must exist on ConversationService"
    )


def test_add_message_scoped_signature() -> None:
    method = getattr(ConversationService, "add_message_scoped", None)
    assert method is not None, "add_message_scoped not found"
    sig = inspect.signature(method)
    params = sig.parameters
    assert "conversation_id" in params
    assert "user_id" in params
    assert "role" in params
    assert "content" in params


def test_add_message_scoped_is_async() -> None:
    method = getattr(ConversationService, "add_message_scoped", None)
    assert method is not None, "add_message_scoped not found"
    assert inspect.iscoroutinefunction(method)


def test_agentic_search_request_has_conversation_id() -> None:
    from harmony.api.routes.agentic_search import AgenticSearchRequest

    r = AgenticSearchRequest(query="test")
    assert hasattr(r, "conversation_id")
    assert r.conversation_id is None


def test_agentic_search_request_has_model() -> None:
    from harmony.api.routes.agentic_search import AgenticSearchRequest

    r = AgenticSearchRequest(query="test")
    assert hasattr(r, "model")
    assert r.model is None
