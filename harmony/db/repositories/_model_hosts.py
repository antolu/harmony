from __future__ import annotations

import psycopg_pool

from ..models import ModelHostCreateData, ModelHostRow

_ALLOWED_HOST_UPDATE_COLUMNS = frozenset({"name", "url", "host_type"})


class ModelHostRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def list_all(self) -> list[ModelHostRow]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, name, url, host_type, created_at, updated_at "
                "FROM model_hosts ORDER BY name"
            )
            columns = [desc.name for desc in (cur.description or [])]
            return [
                ModelHostRow(**dict(zip(columns, row, strict=True)))
                for row in await cur.fetchall()
            ]

    async def get(self, host_id: str) -> ModelHostRow | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute("SELECT * FROM model_hosts WHERE id = %s", (host_id,))
            row = await cur.fetchone()
            if not row:
                return None
            columns = [desc.name for desc in (cur.description or [])]
            return ModelHostRow(**dict(zip(columns, row, strict=True)))

    async def create(self, data: ModelHostCreateData) -> ModelHostRow:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO model_hosts (name, url, host_type) "
                    "VALUES (%s, %s, %s) "
                    "RETURNING id, name, url, host_type, created_at, updated_at",
                    (data.name, data.url, data.host_type),
                )
                row = await cur.fetchone()
        if not row:
            msg = f"Insert for model_hosts name={data.name!r} returned no rows"
            raise RuntimeError(msg)
        columns = ["id", "name", "url", "host_type", "created_at", "updated_at"]
        return ModelHostRow(**dict(zip(columns, row, strict=True)))

    async def update(
        self, host_id: str, fields: dict[str, object]
    ) -> ModelHostRow | None:
        if not fields:
            return await self.get(host_id)
        unknown = set(fields) - _ALLOWED_HOST_UPDATE_COLUMNS
        if unknown:
            msg = f"Unknown update fields: {unknown}"
            raise ValueError(msg)
        set_parts = [f"{k} = %s" for k in fields]
        set_parts.append("updated_at = now()")
        set_clause = ", ".join(set_parts)
        values = list(fields.values())
        values.append(host_id)
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    f"UPDATE model_hosts SET {set_clause} WHERE id = %s "
                    "RETURNING id, name, url, host_type, created_at, updated_at",
                    values,
                )
                row = await cur.fetchone()
        if not row:
            return None
        columns = ["id", "name", "url", "host_type", "created_at", "updated_at"]
        return ModelHostRow(**dict(zip(columns, row, strict=True)))

    async def delete(self, host_id: str) -> bool:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM model_hosts WHERE id = %s", (host_id,))
                return cur.rowcount > 0
