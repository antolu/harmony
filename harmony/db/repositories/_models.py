from __future__ import annotations

import dataclasses

import psycopg_pool

from harmony.api.models.registry import ModelRegistryRow, ModelType


@dataclasses.dataclass
class ModelCreateData:
    name: str
    provider: str
    model_id: str
    model_type: ModelType
    api_key_id: str | None
    cost_per_token: float | None
    enabled: bool
    model_host_id: str | None


class ModelPolicyRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def assign_role(self, model_id: str, harmony_role: str) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "INSERT INTO model_policy (model_id, harmony_role) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (model_id, harmony_role),
            )

    async def remove_role(self, model_id: str, harmony_role: str) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "DELETE FROM model_policy WHERE model_id = %s AND harmony_role = %s",
                (model_id, harmony_role),
            )

    async def get_allowed_roles(self, model_id: str) -> list[str]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT harmony_role FROM model_policy WHERE model_id = %s",
                (model_id,),
            )
            return [row[0] for row in await cur.fetchall()]

    async def list_all(self) -> list[dict]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT model_id, harmony_role FROM model_policy ORDER BY model_id"
            )
            rows = await cur.fetchall()
        by_model: dict[str, list[str]] = {}
        for model_id, role in rows:
            by_model.setdefault(model_id, []).append(role)
        return [
            {"model_id": mid, "allowed_roles": roles} for mid, roles in by_model.items()
        ]


_ALLOWED_MODEL_UPDATE_COLUMNS = frozenset({
    "name",
    "provider",
    "model_id",
    "model_type",
    "api_key_id",
    "cost_per_token",
    "enabled",
    "model_host_id",
})


class ModelRegistryRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def list_all(self) -> list[ModelRegistryRow]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, name, provider, model_id, model_type, api_key_id, "
                "allowed_groups, cost_per_token, enabled, model_host_id, created_at, updated_at "
                "FROM model_registry ORDER BY model_type, name"
            )
            columns = [desc.name for desc in (cur.description or [])]
            return [
                ModelRegistryRow(**dict(zip(columns, row, strict=True)))
                for row in await cur.fetchall()
            ]

    async def get(self, model_id_pk: str) -> ModelRegistryRow | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT * FROM model_registry WHERE id = %s",
                (model_id_pk,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            columns = [desc.name for desc in (cur.description or [])]
            return ModelRegistryRow(**dict(zip(columns, row, strict=True)))

    async def get_by_name(self, name: str) -> ModelRegistryRow | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT * FROM model_registry WHERE name = %s",
                (name,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            columns = [desc.name for desc in (cur.description or [])]
            return ModelRegistryRow(**dict(zip(columns, row, strict=True)))

    async def create(self, data: ModelCreateData) -> ModelRegistryRow:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO model_registry
                        (name, provider, model_id, model_type, api_key_id,
                         cost_per_token, enabled, model_host_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, name, provider, model_id, model_type, api_key_id,
                              allowed_groups, cost_per_token, enabled, model_host_id,
                              created_at, updated_at
                    """,
                    (
                        data.name,
                        data.provider,
                        data.model_id,
                        data.model_type,
                        data.api_key_id,
                        data.cost_per_token,
                        data.enabled,
                        data.model_host_id,
                    ),
                )
                row = await cur.fetchone()
        if not row:
            msg = f"Insert for model_registry name={data.name!r} returned no rows"
            raise RuntimeError(msg)
        columns = [
            "id",
            "name",
            "provider",
            "model_id",
            "model_type",
            "api_key_id",
            "allowed_groups",
            "cost_per_token",
            "enabled",
            "model_host_id",
            "created_at",
            "updated_at",
        ]
        return ModelRegistryRow(**dict(zip(columns, row, strict=True)))

    async def update(
        self, model_pk: str, fields: dict[str, object]
    ) -> ModelRegistryRow | None:
        if not fields:
            return await self.get(model_pk)
        unknown = set(fields) - _ALLOWED_MODEL_UPDATE_COLUMNS
        if unknown:
            msg = f"Unknown update fields: {unknown}"
            raise ValueError(msg)
        set_parts = [f"{k} = %s" for k in fields]
        set_parts.append("updated_at = now()")
        set_clause = ", ".join(set_parts)
        values = list(fields.values())
        values.append(model_pk)
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    f"UPDATE model_registry SET {set_clause} WHERE id = %s "
                    "RETURNING id, name, provider, model_id, model_type, api_key_id, "
                    "allowed_groups, cost_per_token, enabled, model_host_id, "
                    "created_at, updated_at",
                    values,
                )
                row = await cur.fetchone()
        if not row:
            return None
        columns = [
            "id",
            "name",
            "provider",
            "model_id",
            "model_type",
            "api_key_id",
            "allowed_groups",
            "cost_per_token",
            "enabled",
            "model_host_id",
            "created_at",
            "updated_at",
        ]
        return ModelRegistryRow(**dict(zip(columns, row, strict=True)))

    async def delete(self, model_pk: str) -> bool:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM model_registry WHERE id = %s",
                    (model_pk,),
                )
                return cur.rowcount > 0

    async def get_active_by_type(self, model_type: ModelType) -> list[ModelRegistryRow]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, name, provider, model_id, model_type, api_key_id, "
                "allowed_groups, cost_per_token, enabled, model_host_id, "
                "created_at, updated_at "
                "FROM model_registry WHERE model_type = %s AND enabled = true",
                (model_type,),
            )
            columns = [desc.name for desc in (cur.description or [])]
            return [
                ModelRegistryRow(**dict(zip(columns, row, strict=True)))
                for row in await cur.fetchall()
            ]

    async def count_by_type(self, model_type: ModelType) -> int:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM model_registry WHERE model_type = %s",
                (model_type,),
            )
            row = await cur.fetchone()
            return int(row[0]) if row else 0

    async def disable_others_of_type(
        self, model_type: ModelType, except_id: str
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE model_registry SET enabled = false, updated_at = now() "
                    "WHERE model_type = %s AND id != %s AND enabled = true",
                    (model_type, except_id),
                )

    async def count_models_using_host(self, host_id: str) -> int:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM model_registry WHERE model_host_id = %s",
                (host_id,),
            )
            row = await cur.fetchone()
            return int(row[0]) if row else 0

    async def count_models_by_host(self) -> dict[str, int]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT model_host_id, COUNT(*) FROM model_registry "
                "WHERE model_host_id IS NOT NULL GROUP BY model_host_id",
            )
            rows = await cur.fetchall()
            return {str(row[0]): int(row[1]) for row in rows}

    async def count_models_using_key(self, key_id: str) -> int:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM model_registry WHERE api_key_id = %s",
                (key_id,),
            )
            row = await cur.fetchone()
            return int(row[0]) if row else 0

    async def count_models_by_key(self) -> dict[str, int]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT api_key_id, COUNT(*) FROM model_registry "
                "WHERE api_key_id IS NOT NULL GROUP BY api_key_id",
            )
            rows = await cur.fetchall()
            return {str(row[0]): int(row[1]) for row in rows}

    async def disable_models_using_host(self, host_id: str) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE model_registry SET model_host_id = NULL, enabled = false, "
                    "updated_at = now() WHERE model_host_id = %s",
                    (host_id,),
                )

    async def unlink_key_and_disable(self, key_id: str) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE model_registry SET api_key_id = NULL, enabled = false, updated_at = now() "
                    "WHERE api_key_id = %s",
                    (key_id,),
                )
