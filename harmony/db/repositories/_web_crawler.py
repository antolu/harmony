from __future__ import annotations

import builtins
import dataclasses
import json
from datetime import datetime

import psycopg_pool
import pydantic


class SafetyListsRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def load_all(self) -> tuple[list[str], list[str]]:
        allow: list[str] = []
        deny: list[str] = []
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute("SELECT pattern, list_type FROM safety_lists")
            async for row in cur:
                if row[1] == "allow":
                    allow.append(row[0])
                else:
                    deny.append(row[0])
        return allow, deny

    async def add_pattern(self, pattern: str, list_type: str) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "INSERT INTO safety_lists (pattern, list_type) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (pattern, list_type),
            )

    async def remove_pattern(self, pattern: str) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "DELETE FROM safety_lists WHERE pattern = %s", (pattern,)
            )


@dataclasses.dataclass
class CrawlConfigData:
    id: str
    name: str
    description: str | None
    config_json: dict[str, pydantic.JsonValue]
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class CrawlConfigRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def list(self) -> list[CrawlConfigData]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, name, description, config_json, created_by, created_at, updated_at "
                "FROM crawl_configs ORDER BY name"
            )
            columns = [desc.name for desc in (cur.description or [])]
            return [
                CrawlConfigData(**dict(zip(columns, row, strict=False)))
                for row in await cur.fetchall()
            ]

    async def get(self, name: str) -> CrawlConfigData | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, name, description, config_json, created_by, created_at, updated_at "
                "FROM crawl_configs WHERE name = %s",
                (name,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            columns = [desc.name for desc in (cur.description or [])]
            return CrawlConfigData(**dict(zip(columns, row, strict=False)))

    async def create(
        self,
        name: str,
        config_json: dict[str, pydantic.JsonValue],
        description: str | None,
        created_by: str | None,
    ) -> CrawlConfigData:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO crawl_configs (name, config_json, description, created_by)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, name, description, config_json, created_by, created_at, updated_at
                    """,
                    (name, json.dumps(config_json), description, created_by),
                )
                row = await cur.fetchone()
        if not row:
            msg = f"Insert for crawl_config name={name!r} returned no rows"
            raise RuntimeError(msg)
        columns = [
            "id",
            "name",
            "description",
            "config_json",
            "created_by",
            "created_at",
            "updated_at",
        ]
        return CrawlConfigData(**dict(zip(columns, row, strict=False)))

    async def update(
        self,
        name: str,
        config_json: dict[str, pydantic.JsonValue],
        description: str | None,
    ) -> CrawlConfigData | None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE crawl_configs
                    SET config_json = %s, description = %s, updated_at = now()
                    WHERE name = %s
                    RETURNING id, name, description, config_json, created_by, created_at, updated_at
                    """,
                    (json.dumps(config_json), description, name),
                )
                row = await cur.fetchone()
        if not row:
            return None
        columns = [
            "id",
            "name",
            "description",
            "config_json",
            "created_by",
            "created_at",
            "updated_at",
        ]
        return CrawlConfigData(**dict(zip(columns, row, strict=False)))

    async def rename(self, old_name: str, new_name: str) -> bool:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE crawl_configs SET name = %s WHERE name = %s",
                    (new_name, old_name),
                )
                return cur.rowcount > 0

    async def delete(self, name: str) -> bool:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM crawl_configs WHERE name = %s",
                    (name,),
                )
                return cur.rowcount > 0


@dataclasses.dataclass
class CrawlBlacklistData:
    id: str
    pattern: str
    reason: str | None
    created_by: str
    created_at: datetime


class CrawlBlacklistRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def list(self) -> list[CrawlBlacklistData]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT cb.id, cb.pattern, cb.reason,
                       COALESCE(u.display_name, u.email, cb.created_by::text) AS created_by,
                       cb.created_at
                FROM crawl_blacklist cb
                LEFT JOIN users u ON u.id = cb.created_by::uuid
                ORDER BY cb.created_at DESC
                """
            )
            columns = ["id", "pattern", "reason", "created_by", "created_at"]
            return [
                CrawlBlacklistData(**dict(zip(columns, row, strict=False)))
                for row in await cur.fetchall()
            ]

    async def add(
        self, pattern: str, reason: str | None, created_by: str
    ) -> CrawlBlacklistData:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO crawl_blacklist (pattern, reason, created_by, created_at) "
                    "VALUES (%s, %s, %s, now()) RETURNING id, pattern, reason, created_by, created_at",
                    (pattern, reason, created_by),
                )
                row = await cur.fetchone()
        if not row:
            msg = "Insert for crawl_blacklist returned no rows"
            raise RuntimeError(msg)
        columns = ["id", "pattern", "reason", "created_by", "created_at"]
        return CrawlBlacklistData(**dict(zip(columns, row, strict=False)))

    async def remove(self, pattern_id: str) -> bool:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM crawl_blacklist WHERE id = %s",
                    (pattern_id,),
                )
                return cur.rowcount > 0

    async def get_patterns(self) -> builtins.list[str]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute("SELECT pattern FROM crawl_blacklist")
            return [row[0] for row in await cur.fetchall()]
