from __future__ import annotations

import inspect

from harmony.services import ConversationService


def test_list_for_user_exists() -> None:
    assert hasattr(ConversationService, "list_for_user")


def test_update_title_exists() -> None:
    assert hasattr(ConversationService, "update_title")


def test_delete_exists() -> None:
    assert hasattr(ConversationService, "delete")


def test_generate_title_async_exists() -> None:
    assert hasattr(ConversationService, "generate_title_async")


def test_list_for_user_signature() -> None:
    sig = inspect.signature(ConversationService.list_for_user)
    params = sig.parameters
    assert "user_id" in params
    assert "limit" in params
    assert "offset" in params
    assert params["limit"].default == 20
    assert params["offset"].default == 0


def test_update_title_signature() -> None:
    sig = inspect.signature(ConversationService.update_title)
    params = sig.parameters
    assert "conversation_id" in params
    assert "title" in params
    assert "user_id" in params


def test_delete_signature() -> None:
    sig = inspect.signature(ConversationService.delete)
    params = sig.parameters
    assert "conversation_id" in params
    assert "user_id" in params


def test_generate_title_async_signature() -> None:
    sig = inspect.signature(ConversationService.generate_title_async)
    params = sig.parameters
    assert "conversation_id" in params
    assert "user_id" in params
    assert "first_user_msg" in params
    assert "first_assistant_msg" in params
    assert "llm_service" in params


def test_list_for_user_is_async() -> None:
    assert inspect.iscoroutinefunction(ConversationService.list_for_user)


def test_update_title_is_async() -> None:
    assert inspect.iscoroutinefunction(ConversationService.update_title)


def test_delete_is_async() -> None:
    assert inspect.iscoroutinefunction(ConversationService.delete)


def test_generate_title_async_is_async() -> None:
    assert inspect.iscoroutinefunction(ConversationService.generate_title_async)
