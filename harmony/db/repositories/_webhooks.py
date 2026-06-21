from __future__ import annotations

import builtins
import dataclasses
import json
from datetime import datetime

import psycopg_pool


@dataclasses.dataclass
class WebhookDeliveryData:
    webhook_id: str
    event: str
    status: str
    attempts: int
    error: str | None
    delivered_at: datetime | None


@dataclasses.dataclass(kw_only=True)
class WebhookData:
    id: str
    url: str
    events: list[str]
    enabled: bool
    created_by: str
    created_at: datetime
    secret_encrypted: str | None = None


class WebhookRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def list(self) -> list[WebhookData]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, url, events, enabled, created_by, created_at FROM webhooks ORDER BY created_at DESC"
            )
            columns = ["id", "url", "events", "enabled", "created_by", "created_at"]
            return [
                WebhookData(**dict(zip(columns, row, strict=False)))
                for row in await cur.fetchall()
            ]

    async def get(self, webhook_id: str) -> WebhookData | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, url, events, enabled, secret_encrypted, created_by, created_at FROM webhooks WHERE id = %s",
                (webhook_id,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            columns = [
                "id",
                "url",
                "events",
                "enabled",
                "secret_encrypted",
                "created_by",
                "created_at",
            ]
            return WebhookData(**dict(zip(columns, row, strict=False)))

    async def create(
        self,
        url: str,
        secret_encrypted: str | None,
        events: builtins.list[str],
        created_by: str,
    ) -> WebhookData:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO webhooks (url, secret_encrypted, events, enabled, created_by)
                    VALUES (%s, %s, %s, true, %s)
                    RETURNING id, url, events, enabled, secret_encrypted, created_by, created_at
                    """,
                    (url, secret_encrypted, json.dumps(events), created_by),
                )
                row = await cur.fetchone()
        if not row:
            msg = "Insert for webhook returned no rows"
            raise RuntimeError(msg)
        columns = [
            "id",
            "url",
            "events",
            "enabled",
            "secret_encrypted",
            "created_by",
            "created_at",
        ]
        return WebhookData(**dict(zip(columns, row, strict=False)))

    async def delete(self, webhook_id: str) -> bool:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM webhooks WHERE id = %s", (webhook_id,))
                return cur.rowcount > 0

    async def get_for_event(self, event: str) -> builtins.list[WebhookData]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, url, events, enabled, secret_encrypted, created_by, created_at FROM webhooks WHERE enabled = true AND events @> %s::jsonb",
                (json.dumps([event]),),
            )
            columns = [
                "id",
                "url",
                "events",
                "enabled",
                "secret_encrypted",
                "created_by",
                "created_at",
            ]
            return [
                WebhookData(**dict(zip(columns, row, strict=False)))
                for row in await cur.fetchall()
            ]

    async def record_delivery(self, data: WebhookDeliveryData) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                """
                INSERT INTO webhook_deliveries (webhook_id, event, status, attempts, last_error, delivered_at, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, now())
                """,
                (
                    data.webhook_id,
                    data.event,
                    data.status,
                    data.attempts,
                    data.error,
                    data.delivered_at,
                ),
            )
