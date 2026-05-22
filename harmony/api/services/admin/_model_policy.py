from __future__ import annotations

import psycopg_pool

from harmony.db.repositories import ModelPolicyRepo


class ModelPolicyStore:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    def _repo(self) -> ModelPolicyRepo:
        return ModelPolicyRepo(self._pool)

    async def get_allowed_roles(self, model_id: str) -> list[str]:
        return await self._repo().get_allowed_roles(model_id)

    async def assign_role(self, model_id: str, harmony_role: str) -> None:
        await self._repo().assign_role(model_id, harmony_role)

    async def remove_role(self, model_id: str, harmony_role: str) -> None:
        await self._repo().remove_role(model_id, harmony_role)

    async def list_all(self) -> list[dict]:
        return await self._repo().list_all()
