from __future__ import annotations

import typing
import uuid


class ConversationService:
    def __init__(self) -> None:
        # In-memory storage: {conversation_id: [messages]}
        self.conversations: dict[str, list[dict[str, typing.Any]]] = {}

    def create(self) -> str:
        """
        Create a new conversation.

        Returns:
            New conversation ID
        """
        conversation_id = str(uuid.uuid4())
        self.conversations[conversation_id] = []
        return conversation_id

    def get_messages(self, conversation_id: str) -> list[dict[str, typing.Any]]:
        """
        Get all messages for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            List of messages with role and content
        """
        return self.conversations.get(conversation_id, [])

    def add_message(
        self, conversation_id: str, role: str, content: str | dict[str, typing.Any]
    ) -> None:
        """
        Add a message to a conversation.

        Args:
            conversation_id: Conversation ID
            role: Message role (user, assistant, system, tool)
            content: Message content
        """
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []

        message: dict[str, typing.Any] = {"role": role, "content": content}
        self.conversations[conversation_id].append(message)

    def add_tool_call(
        self,
        conversation_id: str,
        tool_calls: list[dict[str, typing.Any]],
    ) -> None:
        """
        Add assistant message with tool calls.

        Args:
            conversation_id: Conversation ID
            tool_calls: List of tool call objects
        """
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []

        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": tool_calls,
        }
        self.conversations[conversation_id].append(message)

    def add_tool_response(
        self, conversation_id: str, tool_call_id: str, name: str, content: str
    ) -> None:
        """
        Add tool response message.

        Args:
            conversation_id: Conversation ID
            tool_call_id: ID of the tool call this responds to
            name: Tool function name
            content: Tool response content
        """
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []

        message = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": name,
            "content": content,
        }
        self.conversations[conversation_id].append(message)

    def clear(self, conversation_id: str) -> None:
        """Clear conversation history."""
        if conversation_id in self.conversations:
            self.conversations[conversation_id] = []
