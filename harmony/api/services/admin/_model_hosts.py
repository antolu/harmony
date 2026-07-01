from __future__ import annotations

import dataclasses
import typing

import psycopg_pool

from harmony.api.services.admin._audit_log import AuditLogService
from harmony.api.services.admin._models import ModelHostRow
from harmony.db.repositories import (
    ModelHostCreateData,
    ModelHostRepo,
    ModelRegistryRepo,
)

HostType = typing.Literal["ollama", "vllm"]


@dataclasses.dataclass
class DeleteResult:
    blocked: bool
    model_count: int = 0


class ModelHostService:
    def __init__(self) -> None:
        self._repo: ModelHostRepo | None = None
        self._model_repo: ModelRegistryRepo | None = None
        self._audit_log: AuditLogService | None = None

    async def initialize(
        self,
        pool: psycopg_pool.AsyncConnectionPool,
        model_repo: ModelRegistryRepo,
        audit_log_service: AuditLogService,
    ) -> None:
        self._repo = ModelHostRepo(pool)
        self._model_repo = model_repo
        self._audit_log = audit_log_service

    @property
    def _r(self) -> ModelHostRepo:
        if self._repo is None:
            msg = "ModelHostService not initialized"
            raise RuntimeError(msg)
        return self._repo

    @property
    def _mr(self) -> ModelRegistryRepo:
        if self._model_repo is None:
            msg = "ModelHostService not initialized"
            raise RuntimeError(msg)
        return self._model_repo

    async def list_all(self) -> list[ModelHostRow]:
        rows = await self._r.list_all()
        counts = await self._mr.count_models_by_host()
        return [
            dataclasses.replace(row, model_count=counts.get(str(row.id), 0))
            for row in rows
        ]

    async def get(self, host_id: str) -> ModelHostRow | None:
        return await self._r.get(host_id)

    async def create(
        self, *, name: str, url: str, host_type: str, created_by: str
    ) -> ModelHostRow:
        if host_type not in typing.get_args(HostType):
            msg = f"Invalid host_type: {host_type}. Must be one of {typing.get_args(HostType)}"
            raise ValueError(msg)
        row = await self._r.create(
            ModelHostCreateData(name=name, url=url, host_type=host_type)
        )
        if self._audit_log:
            await self._audit_log.record(
                user_id=created_by,
                action="model_host_created",
                entity_type="model_host",
                entity_id=str(row.id),
                details={"name": name, "host_type": host_type},
            )
        return row

    async def update(
        self, host_id: str, fields: dict[str, object], *, updated_by: str
    ) -> ModelHostRow | None:
        if "host_type" in fields and fields["host_type"] not in typing.get_args(
            HostType
        ):
            msg = f"Invalid host_type: {fields['host_type']}. Must be one of {typing.get_args(HostType)}"
            raise ValueError(msg)
        row = await self._r.update(host_id, fields)
        if row and self._audit_log:
            await self._audit_log.record(
                user_id=updated_by,
                action="model_host_updated",
                entity_type="model_host",
                entity_id=host_id,
                details={"fields_changed": list(fields.keys())},
            )
        return row

    async def delete(
        self, host_id: str, *, force: bool, deleted_by: str
    ) -> DeleteResult:
        count = await self._mr.count_models_using_host(host_id)
        if count > 0 and not force:
            return DeleteResult(blocked=True, model_count=count)
        if force:
            await self._mr.disable_models_using_host(host_id)
        await self._r.delete(host_id)
        if self._audit_log:
            await self._audit_log.record(
                user_id=deleted_by,
                action="model_host_deleted",
                entity_type="model_host",
                entity_id=host_id,
                details={"force": force, "model_count": count},
            )
        return DeleteResult(blocked=False, model_count=count)
