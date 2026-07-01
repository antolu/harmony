from __future__ import annotations

import dataclasses

import psycopg_pool

from harmony.api.services.admin._models import LLMApiKeyRow


@dataclasses.dataclass
class LLMApiKeyCreateData:
    name: str
    value_encrypted: str


_ALLOWED_KEY_UPDATE_COLUMNS = frozenset({"name", "value_encrypted"})


class LLMApiKeyRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def list_all(self) -> list[LLMApiKeyRow]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, name, value_encrypted, created_at, updated_at "
                "FROM llm_api_keys ORDER BY name"
            )
            columns = [desc.name for desc in (cur.description or [])]
            return [
                LLMApiKeyRow(**dict(zip(columns, row, strict=True)))
                for row in await cur.fetchall()
            ]

    async def get(self, key_id: str) -> LLMApiKeyRow | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute("SELECT * FROM llm_api_keys WHERE id = %s", (key_id,))
            row = await cur.fetchone()
            if not row:
                return None
            columns = [desc.name for desc in (cur.description or [])]
            return LLMApiKeyRow(**dict(zip(columns, row, strict=True)))

    async def create(self, data: LLMApiKeyCreateData) -> LLMApiKeyRow:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO llm_api_keys (name, value_encrypted) "
                    "VALUES (%s, %s) "
                    "RETURNING id, name, value_encrypted, created_at, updated_at",
                    (data.name, data.value_encrypted),
                )
                row = await cur.fetchone()
        if not row:
            msg = f"Insert for llm_api_keys name={data.name!r} returned no rows"
            raise RuntimeError(msg)
        columns = ["id", "name", "value_encrypted", "created_at", "updated_at"]
        return LLMApiKeyRow(**dict(zip(columns, row, strict=True)))

    async def update(
        self, key_id: str, fields: dict[str, object]
    ) -> LLMApiKeyRow | None:
        if not fields:
            return await self.get(key_id)
        unknown = set(fields) - _ALLOWED_KEY_UPDATE_COLUMNS
        if unknown:
            msg = f"Unknown update fields: {unknown}"
            raise ValueError(msg)
        set_parts = [f"{k} = %s" for k in fields]
        set_parts.append("updated_at = now()")
        set_clause = ", ".join(set_parts)
        values = list(fields.values())
        values.append(key_id)
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    f"UPDATE llm_api_keys SET {set_clause} WHERE id = %s "
                    "RETURNING id, name, value_encrypted, created_at, updated_at",
                    values,
                )
                row = await cur.fetchone()
        if not row:
            return None
        columns = ["id", "name", "value_encrypted", "created_at", "updated_at"]
        return LLMApiKeyRow(**dict(zip(columns, row, strict=True)))

    async def delete(self, key_id: str) -> bool:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM llm_api_keys WHERE id = %s", (key_id,))
                return cur.rowcount > 0
