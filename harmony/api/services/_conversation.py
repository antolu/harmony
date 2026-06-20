from __future__ import annotations

import asyncio
import datetime
import json
import logging
import typing
import uuid

import psycopg_pool
import pydantic
from fastapi import HTTPException

logger = logging.getLogger(__name__)


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


class ConversationListItem(typing.TypedDict):
    id: str
    title: str | None
    mode: str
    updated_at: datetime.datetime
    message_count: int


class ConversationService:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def create(self, user_id: str | None = None, mode: str = "search") -> str:
        conversation_id = str(uuid.uuid4())
        if user_id is not None:
            async with self._pool.connection() as conn:
                await conn.set_autocommit(True)
                await conn.execute(
                    "INSERT INTO conversations (id, user_id, messages, updated_at, mode) VALUES (%s, %s, '[]'::jsonb, now(), %s)",
                    (conversation_id, user_id, mode),
                )
        return conversation_id

    async def get_messages(
        self, conversation_id: str, user_id: str | None = None
    ) -> list[dict[str, pydantic.JsonValue]] | None:
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
                return None
            return row[0]

    async def list_for_user(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> tuple[list[ConversationListItem], int]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM conversations WHERE user_id = %s",
                (user_id,),
            )
            count_row = await cur.fetchone()
            total_count: int = count_row[0] if count_row else 0

            await cur.execute(
                """
                SELECT id, title, mode, updated_at,
                       jsonb_array_length(messages) AS message_count
                FROM conversations
                WHERE user_id = %s
                ORDER BY updated_at DESC
                LIMIT %s OFFSET %s
                """,
                (user_id, limit, offset),
            )
            rows = await cur.fetchall()
            result = [
                {
                    "id": row[0],
                    "title": row[1],
                    "mode": row[2],
                    "updated_at": row[3],
                    "message_count": row[4],
                }
                for row in rows
            ]
        return typing.cast(list[ConversationListItem], result), total_count

    async def update_title(
        self, conversation_id: str, title: str, user_id: str
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            result = await conn.execute(
                "UPDATE conversations SET title = %s, updated_at = now() WHERE id = %s AND user_id = %s",
                (title, conversation_id, user_id),
            )
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Conversation not found")

    async def delete(self, conversation_id: str, user_id: str) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            result = await conn.execute(
                "DELETE FROM conversations WHERE id = %s AND user_id = %s",
                (conversation_id, user_id),
            )
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Conversation not found")

    async def _do_generate_title(
        self,
        conversation_id: str,
        user_id: str,
        first_user_msg: str,
        llm_service: typing.Any,
    ) -> None:
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

    async def _store_title_if_unset(
        self, conversation_id: str, user_id: str, title: str
    ) -> None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT title FROM conversations WHERE id = %s AND user_id = %s",
                (conversation_id, user_id),
            )
            row = await cur.fetchone()

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
        llm_service: typing.Any,
    ) -> None:
        if user_id is None:
            return
        try:
            await self._do_generate_title(
                conversation_id, user_id, first_user_msg, llm_service
            )
        except Exception as e:
            logger.warning(
                "generate_title_async: failed for conversation %s: %s",
                conversation_id,
                e,
            )

    async def add_message(
        self, conversation_id: str, role: str, content: str | None
    ) -> None:
        message: ChatMessage = {"role": role, "content": content}
        await self._upsert_message(conversation_id, message)

    async def add_message_scoped(
        self,
        conversation_id: str,
        user_id: str | None,
        role: str,
        content: str | None,
    ) -> None:
        if user_id is not None:
            async with self._pool.connection() as conn, conn.cursor() as cur:
                await cur.execute(
                    "SELECT COUNT(*) FROM conversations WHERE id = %s AND user_id = %s",
                    (conversation_id, user_id),
                )
                row = await cur.fetchone()
                count = row[0] if row else 0
            if count == 0:
                raise HTTPException(
                    status_code=403, detail="Conversation not owned by this user"
                )
        await self.add_message(conversation_id, role, content)

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
