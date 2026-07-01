from __future__ import annotations

import inspect
import pathlib


def test_generate_title_async_has_llm_service_param() -> None:
    from harmony.services import ConversationService

    method = getattr(ConversationService, "generate_title_async", None)
    assert method is not None, "generate_title_async must exist on ConversationService"
    sig = inspect.signature(method)
    assert "llm_service" in sig.parameters, (
        "generate_title_async must have llm_service param"
    )


def test_generate_title_async_uses_asyncio_wait_for() -> None:
    src = pathlib.Path("harmony/services/_conversation.py").read_text(encoding="utf-8")
    assert "asyncio.wait_for" in src, (
        "asyncio.wait_for not found — timeout=10.0 not implemented"
    )


def test_generate_title_async_has_idempotency_check() -> None:
    src = pathlib.Path("harmony/services/_conversation.py").read_text(encoding="utf-8")
    assert "row[0] is not None" in src or "title IS NULL" in src, (
        "idempotency check not found — must read title before calling update_title"
    )


def test_generate_title_async_returns_early_for_anonymous() -> None:
    src = pathlib.Path("harmony/services/_conversation.py").read_text(encoding="utf-8")
    assert "user_id is None" in src, (
        "generate_title_async must return early when user_id is None"
    )


def test_search_session_helper_calls_generate_title_async() -> None:
    src = pathlib.Path("harmony/api/routes/_search_session.py").read_text(
        encoding="utf-8"
    )
    assert "generate_title_async" in src, (
        "the shared title helper must call generate_title_async"
    )


def test_chat_py_triggers_title_for_new_conversations() -> None:
    src = pathlib.Path("harmony/api/routes/chat.py").read_text(encoding="utf-8")
    assert "maybe_generate_title_event" in src, (
        "chat.py must trigger title generation via the shared helper"
    )
    assert "is_new_conversation" in src, (
        "chat.py must only trigger title generation for new conversations"
    )


def test_agentic_search_py_triggers_title_for_new_conversations() -> None:
    src = pathlib.Path("harmony/api/routes/agentic_search.py").read_text(
        encoding="utf-8"
    )
    assert "maybe_generate_title_event" in src, (
        "agentic_search.py must trigger title generation via the shared helper"
    )
    assert "is_new_conversation" in src, (
        "agentic_search.py must only trigger title generation for new conversations"
    )
