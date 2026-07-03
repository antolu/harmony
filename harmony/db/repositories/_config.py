from __future__ import annotations

import json

import psycopg_pool
import pydantic

from ..models import IndexerConfigData, ServiceConfigData


class ServiceConfigRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def get(self, key: str) -> ServiceConfigData | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT key, value, description, is_configured, validated_at, updated_at FROM service_configs WHERE key = %s",
                (key,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            return ServiceConfigData(
                key=row[0],
                value=row[1],
                description=row[2],
                is_configured=row[3],
                validated_at=row[4],
                updated_at=row[5],
            )

    async def get_all(self) -> list[ServiceConfigData]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT key, value, description, is_configured, validated_at, updated_at FROM service_configs"
            )
            columns = [
                "key",
                "value",
                "description",
                "is_configured",
                "validated_at",
                "updated_at",
            ]
            return [
                ServiceConfigData(**dict(zip(columns, row, strict=False)))
                for row in await cur.fetchall()
            ]

    async def upsert(
        self,
        key: str,
        value: str,
        description: str | None = None,
        *,
        validated: bool = True,
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                """
                INSERT INTO service_configs (key, value, description, is_configured, validated_at)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    description = EXCLUDED.description,
                    is_configured = EXCLUDED.is_configured,
                    validated_at = CASE WHEN EXCLUDED.is_configured THEN CURRENT_TIMESTAMP ELSE service_configs.validated_at END,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, value, description, validated),
            )

    async def is_configured(self) -> bool:
        """Check if all required services are configured."""
        required_services = 2  # elasticsearch_url and redis_url
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT COUNT(*) FROM service_configs
                WHERE key IN ('elasticsearch_url', 'redis_url')
                AND is_configured = true
                """
            )
            row = await cur.fetchone()
            return row[0] == required_services if row else False


class IndexerConfigRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def get(self) -> IndexerConfigData | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, config_json, updated_by, updated_at FROM indexer_config LIMIT 1"
            )
            row = await cur.fetchone()
            if not row:
                return None
            columns = [desc.name for desc in (cur.description or [])]
            return IndexerConfigData(**dict(zip(columns, row, strict=False)))

    async def upsert(
        self,
        config_json: dict[str, pydantic.JsonValue],
        updated_by: str | None,
    ) -> IndexerConfigData:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM indexer_config")
                await cur.execute(
                    """
                    INSERT INTO indexer_config (config_json, updated_by)
                    VALUES (%s, %s)
                    RETURNING id, config_json, updated_by, updated_at
                    """,
                    (json.dumps(config_json), updated_by),
                )
                row = await cur.fetchone()
        if not row:
            msg = "Insert for indexer_config returned no rows"
            raise RuntimeError(msg)
        columns = ["id", "config_json", "updated_by", "updated_at"]
        return IndexerConfigData(**dict(zip(columns, row, strict=False)))
