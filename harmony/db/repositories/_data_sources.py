from __future__ import annotations

import dataclasses
import json
from datetime import datetime

import psycopg_pool
import pydantic


@dataclasses.dataclass
class DataSourceData:
    id: str
    name: str
    provider_type: str
    config: dict[str, pydantic.JsonValue]
    description: str | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime
    last_run_at: datetime | None
    last_run_status: str | None
    last_run_doc_count: int | None


_DATA_SOURCE_COLUMNS = (
    "id, name, provider_type, config, description, created_by, "
    "created_at, updated_at, last_run_at, last_run_status, last_run_doc_count"
)


class DataSourcesRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def list_all(self) -> list[DataSourceData]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                f"SELECT {_DATA_SOURCE_COLUMNS} FROM data_sources ORDER BY name"
            )
            columns = [desc.name for desc in (cur.description or [])]
            return [
                DataSourceData(**dict(zip(columns, row, strict=False)))
                for row in await cur.fetchall()
            ]

    async def get(self, data_source_id: str) -> DataSourceData | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                f"SELECT {_DATA_SOURCE_COLUMNS} FROM data_sources WHERE id = %s",
                (data_source_id,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            columns = [desc.name for desc in (cur.description or [])]
            return DataSourceData(**dict(zip(columns, row, strict=False)))

    async def create(
        self,
        name: str,
        provider_type: str,
        config_data: dict[str, pydantic.JsonValue],
        description: str | None,
        created_by: str | None,
    ) -> DataSourceData:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    f"""
                    INSERT INTO data_sources (name, provider_type, config, description, created_by)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING {_DATA_SOURCE_COLUMNS}
                    """,
                    (
                        name,
                        provider_type,
                        json.dumps(config_data),
                        description,
                        created_by,
                    ),
                )
                row = await cur.fetchone()
                columns = [desc.name for desc in (cur.description or [])]
        if not row:
            msg = f"Insert for data_source name={name!r} returned no rows"
            raise RuntimeError(msg)
        return DataSourceData(**dict(zip(columns, row, strict=False)))

    async def update(
        self,
        data_source_id: str,
        name: str,
        config_data: dict[str, pydantic.JsonValue],
        description: str | None,
    ) -> DataSourceData | None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    f"""
                    UPDATE data_sources
                    SET name = %s, config = %s, description = %s, updated_at = now()
                    WHERE id = %s
                    RETURNING {_DATA_SOURCE_COLUMNS}
                    """,
                    (name, json.dumps(config_data), description, data_source_id),
                )
                row = await cur.fetchone()
                columns = [desc.name for desc in (cur.description or [])]
        if not row:
            return None
        return DataSourceData(**dict(zip(columns, row, strict=False)))

    async def delete(self, data_source_id: str) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "DELETE FROM data_sources WHERE id = %s", (data_source_id,)
            )

    async def create_if_not_exists(
        self,
        name: str,
        provider_type: str,
        config_data: dict[str, pydantic.JsonValue],
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                """
                INSERT INTO data_sources (name, provider_type, config)
                VALUES (%s, %s, %s)
                ON CONFLICT (name) DO NOTHING
                """,
                (name, provider_type, json.dumps(config_data)),
            )

    async def update_last_run(
        self,
        data_source_id: str,
        status: str,
        doc_count: int | None,
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                """
                UPDATE data_sources
                SET last_run_at = now(), last_run_status = %s, last_run_doc_count = %s
                WHERE id = %s
                """,
                (status, doc_count, data_source_id),
            )


class FilesystemStateRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def get_hash(self, data_source_id: str, file_uri: str) -> str | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT content_hash FROM filesystem_state "
                "WHERE data_source_id = %s AND file_uri = %s",
                (data_source_id, file_uri),
            )
            row = await cur.fetchone()
            return row[0] if row else None

    async def upsert(
        self,
        data_source_id: str,
        file_uri: str,
        content_hash: str,
        size_bytes: int | None,
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                """
                INSERT INTO filesystem_state (data_source_id, file_uri, content_hash, size_bytes)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (data_source_id, file_uri) DO UPDATE SET
                    content_hash = EXCLUDED.content_hash,
                    size_bytes = EXCLUDED.size_bytes,
                    indexed_at = now()
                """,
                (data_source_id, file_uri, content_hash, size_bytes),
            )

    async def delete_by_source(self, data_source_id: str) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "DELETE FROM filesystem_state WHERE data_source_id = %s",
                (data_source_id,),
            )

    async def list_uris(self, data_source_id: str) -> list[str]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT file_uri FROM filesystem_state WHERE data_source_id = %s",
                (data_source_id,),
            )
            return [row[0] for row in await cur.fetchall()]

    async def delete_uris(self, data_source_id: str, file_uris: list[str]) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "DELETE FROM filesystem_state WHERE data_source_id = %s AND file_uri = ANY(%s)",
                (data_source_id, file_uris),
            )
