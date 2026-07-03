from __future__ import annotations

import asyncio
import json
import logging
import typing
import uuid

import pydantic

from harmony.db.models import ConversationListItem
from harmony.db.repositories import ConversationRepo
from harmony.exceptions import PermissionDeniedError, ResourceNotFoundError

from ._llm import LLMService

logger = logging.getLogger(__name__)


class ChatMessage(typing.TypedDict):
    role: str
    content: str | None
    trace_id: typing.NotRequired[str]


class ToolCallDict(typing.TypedDict):
    id: str
    type: str
    function: dict[str, str]


class AssistantToolCallMessage(typing.TypedDict):
    role: str
    content: None
    tool_calls: list[ToolCallDict]


class ToolResponseMessage(typing.TypedDict):
    role: str
    tool_call_id: str
    name: str
    content: str


class ConversationService:
    def __init__(self, repo: ConversationRepo) -> None:
        self._repo = repo

    async def create(self, user_id: str | None = None, mode: str = "search") -> str:
        conversation_id = str(uuid.uuid4())
        if user_id is not None:
            await self._repo.create(conversation_id, user_id, mode)
        return conversation_id

    async def get_messages(
        self, conversation_id: str, user_id: str | None = None
    ) -> list[dict[str, pydantic.JsonValue]] | None:
        return await self._repo.get_messages(conversation_id, user_id)

    async def list_for_user(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> tuple[list[ConversationListItem], int]:
        total_count = await self._repo.count_for_user(user_id)
        result = await self._repo.list_for_user(user_id, limit, offset)
        return result, total_count

    async def update_title(
        self, conversation_id: str, title: str, user_id: str
    ) -> None:
        if await self._repo.update_title(conversation_id, title, user_id) == 0:
            msg = "Conversation not found"
            raise ResourceNotFoundError(msg)

    async def delete(self, conversation_id: str, user_id: str) -> None:
        if await self._repo.delete(conversation_id, user_id) == 0:
            msg = "Conversation not found"
            raise ResourceNotFoundError(msg)

    async def _do_generate_title(
        self,
        conversation_id: str,
        user_id: str,
        first_user_msg: str,
        llm_service: LLMService,
    ) -> str:
        prompt = (
            f"Summarize this query in 5 words or fewer. Reply with only the title, "
            f"no punctuation.\nQuery: {first_user_msg[:200]}"
        )
        response = await asyncio.wait_for(
            llm_service.complete(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=15,
            ),
            timeout=10.0,
        )
        raw_title: str = response.choices[0].message.content or ""
        title = raw_title.strip().strip('"').strip("'").rstrip(".")
        await self._store_title_if_unset(conversation_id, user_id, title)
        return title

    async def _store_title_if_unset(
        self, conversation_id: str, user_id: str, title: str
    ) -> None:
        row = await self._repo.get_title(conversation_id, user_id)
        if row is None:
            return
        if row[0] is not None:
            return

        await self.update_title(conversation_id, title, user_id)

    async def generate_title_async(
        self,
        conversation_id: str,
        user_id: str | None,
        first_user_msg: str,
        first_assistant_msg: str,
        llm_service: LLMService,
    ) -> str | None:
        if user_id is None:
            return None
        try:
            return await self._do_generate_title(
                conversation_id, user_id, first_user_msg, llm_service
            )
        except Exception as e:
            logger.warning(
                "generate_title_async: failed for conversation %s: %s",
                conversation_id,
                e,
            )
            return None

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str | None,
        trace_id: str | None = None,
    ) -> None:
        message: ChatMessage = {"role": role, "content": content}
        if trace_id is not None:
            message["trace_id"] = trace_id
        await self._upsert_message(conversation_id, message)

    async def add_message_scoped(
        self,
        conversation_id: str,
        user_id: str | None,
        role: str,
        content: str | None,
        trace_id: str | None = None,
    ) -> None:
        if user_id is not None:
            count = await self._repo.count_owned(conversation_id, user_id)
            if count == 0:
                msg = "Conversation not owned by this user"
                raise PermissionDeniedError(msg)
        await self.add_message(conversation_id, role, content, trace_id=trace_id)

    async def add_tool_call(
        self,
        conversation_id: str,
        tool_calls: list[ToolCallDict],
    ) -> None:
        message: AssistantToolCallMessage = {
            "role": "assistant",
            "content": None,
            "tool_calls": tool_calls,
        }
        await self._upsert_message(conversation_id, message)

    async def add_tool_response(
        self, conversation_id: str, tool_call_id: str, name: str, content: str
    ) -> None:
        message: ToolResponseMessage = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": name,
            "content": content,
        }
        await self._upsert_message(conversation_id, message)

    async def _upsert_message(
        self,
        conversation_id: str,
        message: ChatMessage | AssistantToolCallMessage | ToolResponseMessage,
        user_id: str | None = None,
    ) -> None:
        msg_json = json.dumps([message])
        await self._repo.upsert_message(conversation_id, user_id, msg_json)

    async def clear(self, conversation_id: str) -> None:
        await self._repo.clear(conversation_id)

    async def add_trace(
        self, conversation_id: str, events: list[dict[str, typing.Any]]
    ) -> str:
        trace_id = str(uuid.uuid4())
        events_json = json.dumps(events)
        await self._repo.add_trace(trace_id, conversation_id, events_json)
        return trace_id

    async def get_traces(self, conversation_id: str) -> list[dict[str, typing.Any]]:
        return await self._repo.get_traces(conversation_id)
