from __future__ import annotations

import json
import typing
import uuid

import psycopg_pool


class ChatMessage(typing.TypedDict):
    role: str
    content: str | None


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
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def create(self, user_id: str | None = None) -> str:
        conversation_id = str(uuid.uuid4())
        if user_id is not None:
            async with self._pool.connection() as conn:
                await conn.set_autocommit(True)
                await conn.execute(
                    "INSERT INTO conversations (id, user_id, messages, updated_at) VALUES (%s, %s, '[]'::jsonb, now())",
                    (conversation_id, user_id),
                )
        return conversation_id

    async def get_messages(
        self, conversation_id: str, user_id: str | None = None
    ) -> list[dict[str, typing.Any]]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            if user_id is not None:
                await cur.execute(
                    "SELECT messages FROM conversations WHERE id = %s AND user_id = %s",
                    (conversation_id, user_id),
                )
            else:
                await cur.execute(
                    "SELECT messages FROM conversations WHERE id = %s",
                    (conversation_id,),
                )
            row = await cur.fetchone()
            if row is None:
                return []
            return row[0]

    async def add_message(
        self, conversation_id: str, role: str, content: str | None
    ) -> None:
        message: ChatMessage = {"role": role, "content": content}
        await self._upsert_message(conversation_id, message)

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
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                """
                INSERT INTO conversations (id, user_id, messages, updated_at)
                VALUES (%s, %s, %s::jsonb, now())
                ON CONFLICT (id) DO UPDATE
                SET messages = conversations.messages || %s::jsonb,
                    updated_at = now()
                """,
                (conversation_id, user_id, msg_json, msg_json),
            )

    async def clear(self, conversation_id: str) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "UPDATE conversations SET messages = '[]'::jsonb, updated_at = now() WHERE id = %s",
                (conversation_id,),
            )
