from __future__ import annotations

import dataclasses
import json
from datetime import datetime

import psycopg_pool
import pydantic


@dataclasses.dataclass
class AuditEventData:
    id: str
    user_id: str
    user_email: str
    action: str
    entity_type: str
    entity_id: str | None
    details: dict[str, pydantic.JsonValue]
    created_at: datetime


class AuditEventRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def record(
        self,
        user_id: str,
        action: str,
        entity_type: str,
        entity_id: str | None,
        details: dict[str, pydantic.JsonValue],
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "INSERT INTO audit_events (user_id, action, entity_type, entity_id, details, created_at) "
                "VALUES (%s, %s, %s, %s, %s, now())",
                (user_id, action, entity_type, entity_id, json.dumps(details)),
            )

    async def query(
        self,
        user_id: str | None,
        action: str | None,
        days_back: int,
        limit: int,
        offset: int,
    ) -> tuple[list[AuditEventData], int]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT COUNT(*) FROM audit_events ae
                WHERE ae.created_at > now() - interval '1 day' * %s
                  AND (%s::text IS NULL OR ae.user_id = %s)
                  AND (%s::text IS NULL OR ae.action = %s)
                """,
                (days_back, user_id, user_id, action, action),
            )
            count_row = await cur.fetchone()
            total = int(count_row[0]) if count_row else 0
            await cur.execute(
                """
                SELECT ae.id, ae.user_id, COALESCE(u.email, ae.user_id) AS user_email,
                       ae.action, ae.entity_type, ae.entity_id, ae.details, ae.created_at
                FROM audit_events ae
                LEFT JOIN users u ON u.id::text = ae.user_id
                WHERE ae.created_at > now() - interval '1 day' * %s
                  AND (%s::text IS NULL OR ae.user_id = %s)
                  AND (%s::text IS NULL OR ae.action = %s)
                ORDER BY ae.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (days_back, user_id, user_id, action, action, limit, offset),
            )
            columns = [desc.name for desc in (cur.description or [])]
            events = [
                AuditEventData(**dict(zip(columns, row, strict=False)))
                for row in await cur.fetchall()
            ]
            return events, total

    async def cleanup(self, retention_days: int) -> int:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM audit_events WHERE created_at < now() - interval '1 day' * %s",
                    (retention_days,),
                )
                return cur.rowcount
