from __future__ import annotations

import dataclasses
import typing

import psycopg_pool

from harmony.api.models.registry import OllamaHostRow
from harmony.api.services.admin._audit_log import AuditLogService
from harmony.db.repositories import (
    ModelRegistryRepo,
    OllamaHostCreateData,
    OllamaHostRepo,
)

HostType = typing.Literal["ollama", "vllm"]


@dataclasses.dataclass
class DeleteResult:
    blocked: bool
    model_count: int = 0


class OllamaHostService:
    def __init__(self) -> None:
        self._repo: OllamaHostRepo | None = None
        self._model_repo: ModelRegistryRepo | None = None
        self._audit_log: AuditLogService | None = None

    async def initialize(
        self,
        pool: psycopg_pool.AsyncConnectionPool,
        model_repo: ModelRegistryRepo,
        audit_log_service: AuditLogService,
    ) -> None:
        self._repo = OllamaHostRepo(pool)
        self._model_repo = model_repo
        self._audit_log = audit_log_service

    @property
    def _r(self) -> OllamaHostRepo:
        if self._repo is None:
            msg = "OllamaHostService not initialized"
            raise RuntimeError(msg)
        return self._repo

    @property
    def _mr(self) -> ModelRegistryRepo:
        if self._model_repo is None:
            msg = "OllamaHostService not initialized"
            raise RuntimeError(msg)
        return self._model_repo

    async def list_all(self) -> list[OllamaHostRow]:
        return await self._r.list_all()

    async def get(self, host_id: str) -> OllamaHostRow | None:
        return await self._r.get(host_id)

    async def create(
        self, *, name: str, url: str, host_type: str, created_by: str
    ) -> OllamaHostRow:
        if host_type not in typing.get_args(HostType):
            msg = f"Invalid host_type: {host_type}. Must be one of {typing.get_args(HostType)}"
            raise ValueError(msg)
        row = await self._r.create(
            OllamaHostCreateData(name=name, url=url, host_type=host_type)
        )
        if self._audit_log:
            await self._audit_log.record(
                user_id=created_by,
                action="ollama_host_created",
                entity_type="ollama_host",
                entity_id=str(row.id),
                details={"name": name, "host_type": host_type},
            )
        return row

    async def update(
        self, host_id: str, fields: dict[str, object], *, updated_by: str
    ) -> OllamaHostRow | None:
        if "host_type" in fields and fields["host_type"] not in typing.get_args(
            HostType
        ):
            msg = f"Invalid host_type: {fields['host_type']}. Must be one of {typing.get_args(HostType)}"
            raise ValueError(msg)
        row = await self._r.update(host_id, fields)
        if row and self._audit_log:
            await self._audit_log.record(
                user_id=updated_by,
                action="ollama_host_updated",
                entity_type="ollama_host",
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
                action="ollama_host_deleted",
                entity_type="ollama_host",
                entity_id=host_id,
                details={"force": force, "model_count": count},
            )
        return DeleteResult(blocked=False, model_count=count)
