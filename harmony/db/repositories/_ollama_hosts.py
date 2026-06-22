from __future__ import annotations

import dataclasses

import psycopg_pool

from harmony.api.models.registry import OllamaHostRow


@dataclasses.dataclass
class OllamaHostCreateData:
    name: str
    url: str
    host_type: str


_ALLOWED_HOST_UPDATE_COLUMNS = frozenset({"name", "url", "host_type"})


class OllamaHostRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def list_all(self) -> list[OllamaHostRow]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, name, url, host_type, created_at, updated_at "
                "FROM ollama_hosts ORDER BY name"
            )
            columns = [desc.name for desc in (cur.description or [])]
            return [
                OllamaHostRow(**dict(zip(columns, row, strict=True)))
                for row in await cur.fetchall()
            ]

    async def get(self, host_id: str) -> OllamaHostRow | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute("SELECT * FROM ollama_hosts WHERE id = %s", (host_id,))
            row = await cur.fetchone()
            if not row:
                return None
            columns = [desc.name for desc in (cur.description or [])]
            return OllamaHostRow(**dict(zip(columns, row, strict=True)))

    async def create(self, data: OllamaHostCreateData) -> OllamaHostRow:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO ollama_hosts (name, url, host_type) "
                    "VALUES (%s, %s, %s) "
                    "RETURNING id, name, url, host_type, created_at, updated_at",
                    (data.name, data.url, data.host_type),
                )
                row = await cur.fetchone()
        if not row:
            msg = f"Insert for ollama_hosts name={data.name!r} returned no rows"
            raise RuntimeError(msg)
        columns = ["id", "name", "url", "host_type", "created_at", "updated_at"]
        return OllamaHostRow(**dict(zip(columns, row, strict=True)))

    async def update(
        self, host_id: str, fields: dict[str, object]
    ) -> OllamaHostRow | None:
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
                    f"UPDATE ollama_hosts SET {set_clause} WHERE id = %s "
                    "RETURNING id, name, url, host_type, created_at, updated_at",
                    values,
                )
                row = await cur.fetchone()
        if not row:
            return None
        columns = ["id", "name", "url", "host_type", "created_at", "updated_at"]
        return OllamaHostRow(**dict(zip(columns, row, strict=True)))

    async def delete(self, host_id: str) -> bool:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM ollama_hosts WHERE id = %s", (host_id,))
                return cur.rowcount > 0
