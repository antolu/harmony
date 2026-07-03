from __future__ import annotations

import typing

import psycopg_pool
import pydantic

from ..models import ConversationListItem


class ConversationRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def create(self, conversation_id: str, user_id: str, mode: str) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "INSERT INTO conversations (id, user_id, messages, updated_at, mode) VALUES (%s, %s, '[]'::jsonb, now(), %s)",
                (conversation_id, user_id, mode),
            )

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

    async def count_for_user(self, user_id: str) -> int:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM conversations WHERE user_id = %s",
                (user_id,),
            )
            row = await cur.fetchone()
            return row[0] if row else 0

    async def list_for_user(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> list[ConversationListItem]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
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
        return [
            ConversationListItem(
                id=row[0],
                title=row[1],
                mode=row[2],
                updated_at=row[3],
                message_count=row[4],
            )
            for row in rows
        ]

    async def update_title(self, conversation_id: str, title: str, user_id: str) -> int:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            result = await conn.execute(
                "UPDATE conversations SET title = %s, updated_at = now() WHERE id = %s AND user_id = %s",
                (title, conversation_id, user_id),
            )
            return result.rowcount

    async def delete(self, conversation_id: str, user_id: str) -> int:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            result = await conn.execute(
                "DELETE FROM conversations WHERE id = %s AND user_id = %s",
                (conversation_id, user_id),
            )
            return result.rowcount

    async def get_title(
        self, conversation_id: str, user_id: str
    ) -> tuple[str | None] | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT title FROM conversations WHERE id = %s AND user_id = %s",
                (conversation_id, user_id),
            )
            return await cur.fetchone()

    async def count_owned(self, conversation_id: str, user_id: str) -> int:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM conversations WHERE id = %s AND user_id = %s",
                (conversation_id, user_id),
            )
            row = await cur.fetchone()
            return row[0] if row else 0

    async def upsert_message(
        self, conversation_id: str, user_id: str | None, msg_json: str
    ) -> None:
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

    async def add_trace(
        self, trace_id: str, conversation_id: str, events_json: str
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                """
                INSERT INTO conversation_traces (id, conversation_id, events, created_at)
                VALUES (%s, %s, %s::jsonb, now())
                """,
                (trace_id, conversation_id, events_json),
            )

    async def get_traces(self, conversation_id: str) -> list[dict[str, typing.Any]]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, events, created_at
                FROM conversation_traces
                WHERE conversation_id = %s
                ORDER BY created_at ASC
                """,
                (conversation_id,),
            )
            rows = await cur.fetchall()
        return [
            {
                "id": str(row[0]),
                "events": row[1],
                "created_at": row[2].isoformat() if row[2] else None,
            }
            for row in rows
        ]

    async def delete_older_than(self, ttl_days: int) -> int:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM conversations WHERE created_at < now() - interval '1 day' * %s",
                    (ttl_days,),
                )
                return cur.rowcount
