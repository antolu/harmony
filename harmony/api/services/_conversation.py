from __future__ import annotations

import json
import typing
import uuid

import psycopg_pool


class ConversationService:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def create(self) -> str:
        return str(uuid.uuid4())

    async def get_messages(self, conversation_id: str) -> list[dict[str, typing.Any]]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT messages FROM conversations WHERE id = %s",
                (conversation_id,),
            )
            row = await cur.fetchone()
            if row is None:
                return []
            return row[0]

    async def add_message(
        self, conversation_id: str, role: str, content: str | dict[str, typing.Any]
    ) -> None:
        message: dict[str, typing.Any] = {"role": role, "content": content}
        await self._upsert_message(conversation_id, message)

    async def add_tool_call(
        self,
        conversation_id: str,
        tool_calls: list[dict[str, typing.Any]],
    ) -> None:
        message: dict[str, typing.Any] = {
            "role": "assistant",
            "content": None,
            "tool_calls": tool_calls,
        }
        await self._upsert_message(conversation_id, message)

    async def add_tool_response(
        self, conversation_id: str, tool_call_id: str, name: str, content: str
    ) -> None:
        message: dict[str, typing.Any] = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": name,
            "content": content,
        }
        await self._upsert_message(conversation_id, message)

    async def _upsert_message(
        self, conversation_id: str, message: dict[str, typing.Any]
    ) -> None:
        msg_json = json.dumps([message])
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                """
                INSERT INTO conversations (id, messages, updated_at)
                VALUES (%s, %s::jsonb, now())
                ON CONFLICT (id) DO UPDATE
                SET messages = conversations.messages || %s::jsonb,
                    updated_at = now()
                """,
                (conversation_id, msg_json, msg_json),
            )

    async def clear(self, conversation_id: str) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "UPDATE conversations SET messages = '[]'::jsonb, updated_at = now() WHERE id = %s",
                (conversation_id,),
            )
