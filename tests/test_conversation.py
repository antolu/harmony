from __future__ import annotations

from harmony.api.services.conversation import ConversationService

EXPECTED_MESSAGE_COUNT = 2


def test_create_conversation(conversation_service: ConversationService) -> None:
    """Can create a new conversation."""
    conv_id = conversation_service.create()
    assert conv_id is not None
    assert len(conv_id) > 0


def test_add_and_retrieve_messages(conversation_service: ConversationService) -> None:
    """Messages persist in conversation."""
    conv_id = conversation_service.create()
    conversation_service.add_message(conv_id, "user", "Hello")
    conversation_service.add_message(conv_id, "assistant", "Hi there")

    messages = conversation_service.get_messages(conv_id)
    assert len(messages) == EXPECTED_MESSAGE_COUNT
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "Hi there"


def test_conversation_continuity_across_calls(
    conversation_service: ConversationService,
) -> None:
    """Same conversation_id maintains history."""
    conv_id = conversation_service.create()

    conversation_service.add_message(conv_id, "user", "First")
    first_count = len(conversation_service.get_messages(conv_id))

    conversation_service.add_message(conv_id, "user", "Second")
    second_count = len(conversation_service.get_messages(conv_id))

    assert second_count == first_count + 1
    messages = conversation_service.get_messages(conv_id)
    assert messages[0]["content"] == "First"
    assert messages[1]["content"] == "Second"


def test_tool_call_and_response(conversation_service: ConversationService) -> None:
    """Tool calls and responses are stored correctly."""
    conv_id = conversation_service.create()

    tool_calls = [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "search", "arguments": "{}"},
        }
    ]
    conversation_service.add_tool_call(conv_id, tool_calls)
    conversation_service.add_tool_response(
        conv_id, "call_1", "search", '{"results": []}'
    )

    messages = conversation_service.get_messages(conv_id)
    assert len(messages) == EXPECTED_MESSAGE_COUNT
    assert messages[0]["role"] == "assistant"
    assert messages[0]["tool_calls"] == tool_calls
    assert messages[1]["role"] == "tool"
    assert messages[1]["tool_call_id"] == "call_1"
    assert messages[1]["name"] == "search"


def test_clear_conversation(conversation_service: ConversationService) -> None:
    """Conversation can be cleared."""
    conv_id = conversation_service.create()
    conversation_service.add_message(conv_id, "user", "Test")
    assert len(conversation_service.get_messages(conv_id)) == 1

    conversation_service.clear(conv_id)
    assert len(conversation_service.get_messages(conv_id)) == 0


def test_nonexistent_conversation_returns_empty(
    conversation_service: ConversationService,
) -> None:
    """Requesting messages for nonexistent conversation returns empty list."""
    messages = conversation_service.get_messages("nonexistent")
    assert messages == []
