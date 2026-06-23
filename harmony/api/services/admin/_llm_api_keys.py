from __future__ import annotations

import dataclasses
import typing

import psycopg_pool
import pydantic

from harmony.api.models.registry import LLMApiKeyRow
from harmony.api.observability._secret_service import SecretValueService
from harmony.api.services.admin._audit_log import AuditLogService
from harmony.api.services.admin._model_hosts import DeleteResult
from harmony.db.repositories import (
    LLMApiKeyCreateData,
    LLMApiKeyRepo,
    ModelRegistryRepo,
)


class LLMApiKeyService:
    def __init__(self) -> None:
        self._repo: LLMApiKeyRepo | None = None
        self._model_repo: ModelRegistryRepo | None = None
        self._audit_log: AuditLogService | None = None
        self._secrets: SecretValueService | None = None

    async def initialize(
        self,
        pool: psycopg_pool.AsyncConnectionPool,
        model_repo: ModelRegistryRepo,
        audit_log_service: AuditLogService,
        secret_service: SecretValueService,
    ) -> None:
        self._repo = LLMApiKeyRepo(pool)
        self._model_repo = model_repo
        self._audit_log = audit_log_service
        self._secrets = secret_service

    @property
    def _r(self) -> LLMApiKeyRepo:
        if self._repo is None:
            msg = "LLMApiKeyService not initialized"
            raise RuntimeError(msg)
        return self._repo

    @property
    def _mr(self) -> ModelRegistryRepo:
        if self._model_repo is None:
            msg = "LLMApiKeyService not initialized"
            raise RuntimeError(msg)
        return self._model_repo

    @property
    def _s(self) -> SecretValueService:
        if self._secrets is None:
            msg = "LLMApiKeyService not initialized"
            raise RuntimeError(msg)
        return self._secrets

    def _annotate(self, row: LLMApiKeyRow) -> LLMApiKeyRow:
        return dataclasses.replace(
            row,
            value_set=bool(row.value_encrypted),
            value_encrypted=None,
        )

    async def list_all(self) -> list[LLMApiKeyRow]:
        rows = await self._r.list_all()
        counts = await self._mr.count_models_by_key()
        return [
            dataclasses.replace(
                self._annotate(row), model_count=counts.get(str(row.id), 0)
            )
            for row in rows
        ]

    async def get(self, key_id: str) -> LLMApiKeyRow | None:
        row = await self._r.get(key_id)
        if row is None:
            return None
        return self._annotate(row)

    async def create(self, *, name: str, value: str, created_by: str) -> LLMApiKeyRow:
        encrypted = self._s.encrypt(value)
        row = await self._r.create(
            LLMApiKeyCreateData(name=name, value_encrypted=encrypted)
        )
        if self._audit_log:
            await self._audit_log.record(
                user_id=created_by,
                action="llm_api_key_created",
                entity_type="llm_api_key",
                entity_id=str(row.id),
                details={"name": name},
            )
        return self._annotate(row)

    async def update(
        self,
        key_id: str,
        *,
        name: str | None = None,
        value: str | None = None,
        updated_by: str,
    ) -> LLMApiKeyRow | None:
        fields: dict[str, object] = {}
        if name is not None:
            fields["name"] = name
        if value is not None:
            fields["value_encrypted"] = self._s.encrypt(value)

        row = await self._r.update(key_id, fields)
        if row is None:
            return None

        if self._audit_log:
            details_fields = list(fields.keys())
            if "value_encrypted" in details_fields:
                details_fields.remove("value_encrypted")
                details_fields.append("value")
            await self._audit_log.record(
                user_id=updated_by,
                action="llm_api_key_updated",
                entity_type="llm_api_key",
                entity_id=key_id,
                details={
                    "fields_changed": typing.cast(
                        list[pydantic.JsonValue], details_fields
                    )
                },
            )
        return self._annotate(row)

    async def delete(self, key_id: str, *, deleted_by: str) -> DeleteResult:
        count = await self._mr.count_models_using_key(key_id)
        if count > 0:
            await self._mr.unlink_key_and_disable(key_id)
        await self._r.delete(key_id)
        if self._audit_log:
            await self._audit_log.record(
                user_id=deleted_by,
                action="llm_api_key_deleted",
                entity_type="llm_api_key",
                entity_id=key_id,
                details={"model_count": count},
            )
        return DeleteResult(blocked=False, model_count=count)
