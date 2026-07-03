from __future__ import annotations

import typing

import psycopg_pool
import pydantic

from ..models import SearchLogData


class SearchQueryLogRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def record(self, data: SearchLogData) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "INSERT INTO search_query_log (user_id, query, language, result_count, latency_ms, tokens, mode, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, now())",
                (
                    data.user_id,
                    data.query,
                    data.language,
                    data.result_count,
                    data.latency_ms,
                    data.tokens,
                    data.mode,
                ),
            )


class TokenUsageRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def insert_batch(self, events: list[dict]) -> None:
        if not events:
            return
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.executemany(
                    """
                    INSERT INTO token_usage
                        (trace_id, user_id, endpoint, agent_step, model, provider,
                         input_tokens, output_tokens, total_tokens, recorded_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            e.get("trace_id"),
                            e.get("user_id"),
                            e.get("endpoint"),
                            e.get("agent_step"),
                            e.get("model", ""),
                            e.get("provider"),
                            e.get("input_tokens"),
                            e.get("output_tokens"),
                            e.get("total_tokens"),
                            e.get("recorded_at"),
                        )
                        for e in events
                    ],
                )

    async def query(
        self,
        model: str | None = None,
        user_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        conditions = []
        params: list[pydantic.JsonValue] = []

        if model:
            conditions.append("model = %s")
            params.append(model)
        if user_id:
            conditions.append("user_id = %s")
            params.append(user_id)
        if date_from:
            conditions.append("recorded_at >= %s")
            params.append(date_from)
        if date_to:
            conditions.append("recorded_at <= %s")
            params.append(date_to)

        # conditions must only contain static string literals; all user values go into params
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        sql = f"""
            SELECT
                user_id,
                model,
                DATE(recorded_at) AS usage_date,
                SUM(input_tokens) AS input_tokens,
                SUM(output_tokens) AS output_tokens,
                SUM(total_tokens) AS total_tokens
            FROM token_usage
            {where}
            GROUP BY user_id, model, DATE(recorded_at)
            ORDER BY usage_date DESC
            LIMIT %s
        """

        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(sql, params)
            columns = [
                "user_id",
                "model",
                "usage_date",
                "input_tokens",
                "output_tokens",
                "total_tokens",
            ]
            return [
                typing.cast(dict, dict(zip(columns, row, strict=False)))
                for row in await cur.fetchall()
            ]


class MessageFeedbackRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def upsert(
        self, conversation_id: str, message_id: int, user_id: str, rating: str
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                """
                INSERT INTO message_feedback (conversation_id, message_id, user_id, rating)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (conversation_id, message_id, user_id) DO UPDATE SET
                    rating = EXCLUDED.rating,
                    updated_at = now()
                """,
                (conversation_id, message_id, user_id, rating),
            )

    async def get_for_conversation(
        self, conversation_id: str, user_id: str
    ) -> list[dict]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, conversation_id, message_id, user_id, rating, created_at, updated_at
                FROM message_feedback
                WHERE conversation_id = %s AND user_id = %s
                ORDER BY message_id ASC
                """,
                (conversation_id, user_id),
            )
            columns = [desc.name for desc in (cur.description or [])]
            return [
                typing.cast(dict, dict(zip(columns, row, strict=False)))
                for row in await cur.fetchall()
            ]

    async def delete_user_rating(
        self, conversation_id: str, message_id: int, user_id: str
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "DELETE FROM message_feedback WHERE conversation_id = %s AND message_id = %s AND user_id = %s",
                (conversation_id, message_id, user_id),
            )
