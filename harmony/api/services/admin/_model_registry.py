from __future__ import annotations

import contextlib
import dataclasses
import logging
import os
import time
import typing

import litellm
import psycopg_pool
import pydantic
from cryptography.fernet import InvalidToken

from harmony.api.models.registry import (
    LLMApiKeyRow,
    ModelRegistryRow,
    ModelType,
    OllamaHostRow,
)
from harmony.api.observability._secret_service import SecretValueService
from harmony.api.services.admin._audit_log import AuditLogService
from harmony.db.repositories import (
    LLMApiKeyCreateData,
    LLMApiKeyRepo,
    ModelCreateData,
    ModelRegistryRepo,
    OllamaHostRepo,
)

logger = logging.getLogger(__name__)

_SINGLETON_TYPES = {ModelType.embedding, ModelType.reranker, ModelType.vision}

_ENV_OVERRIDES: dict[ModelType, str] = {
    ModelType.llm: "LLM_MODEL",
    ModelType.embedding: "EMBEDDING_MODEL",
    ModelType.reranker: "RERANKER_MODEL",
}


@dataclasses.dataclass
class ConnectivityResult:
    ok: bool = False
    latency_ms: float | None = None
    error: str | None = None


@dataclasses.dataclass
class ManifestResult:
    chat: list[str] = dataclasses.field(default_factory=list)
    embedding: list[str] = dataclasses.field(default_factory=list)
    rerank: list[str] = dataclasses.field(default_factory=list)
    vision: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class ResolvedConnection:
    api_base: str | None
    api_key: str | None


class ModelRegistryService:
    def __init__(self) -> None:
        self._repo: ModelRegistryRepo | None = None
        self._secret_svc: SecretValueService | None = None
        self._audit_log: AuditLogService | None = None
        self._pool: psycopg_pool.AsyncConnectionPool | None = None
        self._ollama_host_repo: OllamaHostRepo | None = None
        self._llm_api_key_repo: LLMApiKeyRepo | None = None

    async def initialize(
        self,
        pool: psycopg_pool.AsyncConnectionPool,
        audit_log_service: AuditLogService,
        secret_service: SecretValueService,
        ollama_host_repo: OllamaHostRepo | None = None,
        llm_api_key_repo: LLMApiKeyRepo | None = None,
    ) -> None:
        self._repo = ModelRegistryRepo(pool)
        self._audit_log = audit_log_service
        self._secret_svc = secret_service
        self._pool = pool
        self._ollama_host_repo = ollama_host_repo
        self._llm_api_key_repo = llm_api_key_repo

    @property
    def _r(self) -> ModelRegistryRepo:
        if self._repo is None:
            msg = "ModelRegistryService not initialized"
            raise RuntimeError(msg)
        return self._repo

    @property
    def _secrets(self) -> SecretValueService:
        if self._secret_svc is None:
            msg = "ModelRegistryService not initialized"
            raise RuntimeError(msg)
        return self._secret_svc

    def _annotate_row(
        self,
        row: ModelRegistryRow,
        ollama_host_row: OllamaHostRow | None = None,
        llm_api_key_row: LLMApiKeyRow | None = None,
    ) -> ModelRegistryRow:
        try:
            model_type: ModelType | None = ModelType(row.model_type)
        except ValueError:
            model_type = None
        env_var = _ENV_OVERRIDES.get(model_type) if model_type else None

        ollama_host = ollama_host_row.url if ollama_host_row else None
        api_key_name = llm_api_key_row.name if llm_api_key_row else None

        return dataclasses.replace(
            row,
            env_override=bool(env_var and os.environ.get(env_var)),
            api_key_set=bool(row.api_key_id),
            litellm_model_id=self._litellm_model_id(row.provider, row.model_id),
            ollama_host=ollama_host,
            api_key_name=api_key_name,
        )

    async def _annotate_row_async(self, row: ModelRegistryRow) -> ModelRegistryRow:
        host_row = None
        key_row = None
        if row.ollama_host_id and self._ollama_host_repo:
            host_row = await self._ollama_host_repo.get(row.ollama_host_id)
        if row.api_key_id and self._llm_api_key_repo:
            key_row = await self._llm_api_key_repo.get(row.api_key_id)
        return self._annotate_row(row, host_row, key_row)

    @staticmethod
    def _litellm_model_id(provider: str, model_id: str) -> str:
        """Return the full LiteLLM model string (provider/model_id).

        model_id in the DB is always the bare name (no provider prefix).
        provider is the LiteLLM provider prefix (e.g. openai, ollama, anthropic).
        """
        return f"{provider}/{model_id}"

    async def list_all(self) -> list[ModelRegistryRow]:
        rows = await self._r.list_all()
        return [await self._annotate_row_async(row) for row in rows]

    async def get(self, model_pk: str) -> ModelRegistryRow | None:
        row = await self._r.get(model_pk)
        if row is None:
            return None
        return await self._annotate_row_async(row)

    async def create(
        self,
        data: ModelCreateData,
        api_key: str | None,
        created_by: str,
    ) -> ModelRegistryRow:
        if api_key:
            if not self._pool:
                msg = "Service not initialized"
                raise RuntimeError(msg)
            key_repo = LLMApiKeyRepo(self._pool)
            key_row = await key_repo.create(
                LLMApiKeyCreateData(
                    name=f"{data.provider} Key",
                    value_encrypted=self._secrets.encrypt(api_key),
                )
            )
            data.api_key_id = key_row.id
        else:
            data.api_key_id = None
        if data.model_type in _SINGLETON_TYPES and data.enabled:
            existing_count = await self._r.count_by_type(data.model_type)
            if existing_count > 0:
                data.enabled = False
        row = await self._r.create(data)
        if self._audit_log:
            await self._audit_log.record(
                user_id=created_by,
                action="model_created",
                entity_type="model_registry",
                entity_id=str(row.id),
                details={
                    "name": data.name,
                    "provider": data.provider,
                    "model_type": data.model_type,
                },
            )
        return await self._annotate_row_async(row)

    async def update(
        self, model_pk: str, fields: dict[str, pydantic.JsonValue], updated_by: str
    ) -> ModelRegistryRow | None:
        fields = dict(fields)
        if "api_key" in fields:
            raw_key = fields.pop("api_key")
            if raw_key:
                if not self._pool:
                    msg = "Service not initialized"
                    raise RuntimeError(msg)
                key_repo = LLMApiKeyRepo(self._pool)
                key_row = await key_repo.create(
                    LLMApiKeyCreateData(
                        name="API Key",
                        value_encrypted=self._secrets.encrypt(str(raw_key)),
                    )
                )
                fields["api_key_id"] = key_row.id
            else:
                fields["api_key_id"] = None
        changed_fields = [k for k in fields if k != "api_key_id"]
        enabling = fields.get("enabled") is True
        if enabling:
            existing = await self._r.get(model_pk)
            if existing:
                try:
                    existing_type = ModelType(existing.model_type)
                except ValueError:
                    existing_type = None
                if existing_type in _SINGLETON_TYPES:
                    await self._r.disable_others_of_type(existing_type, model_pk)
        row = await self._r.update(model_pk, typing.cast(dict[str, object], fields))
        if row is None:
            return None
        if self._audit_log:
            await self._audit_log.record(
                user_id=updated_by,
                action="model_updated",
                entity_type="model_registry",
                entity_id=model_pk,
                details={
                    "fields_changed": typing.cast(
                        list[pydantic.JsonValue], changed_fields
                    )
                },
            )
        return await self._annotate_row_async(row)

    async def delete(self, model_pk: str, deleted_by: str) -> bool:
        result = await self._r.delete(model_pk)
        if result and self._audit_log:
            await self._audit_log.record(
                user_id=deleted_by,
                action="model_deleted",
                entity_type="model_registry",
                entity_id=model_pk,
                details={},
            )
        return result

    def _resolve_test_api_key(
        self, encrypted_key: str | None, *, use_env: bool
    ) -> str | None:
        if use_env or not encrypted_key:
            return None
        return self._secrets.decrypt(encrypted_key)

    async def test_connectivity(self, model_pk: str) -> ConnectivityResult:
        row = await self._r.get(model_pk)
        if row is None:
            return ConnectivityResult(ok=False, error="Model not found")

        provider = row.provider
        model_id = self._litellm_model_id(provider, row.model_id)
        try:
            model_type: ModelType | None = ModelType(row.model_type)
        except ValueError:
            model_type = None
        encrypted_key = None
        if row.api_key_id:
            if not self._pool:
                msg = "Service not initialized"
                raise RuntimeError(msg)
            key_repo = LLMApiKeyRepo(self._pool)
            key_row = await key_repo.get(row.api_key_id)
            if key_row:
                encrypted_key = key_row.value_encrypted

        env_var = _ENV_OVERRIDES.get(model_type) if model_type else None
        use_env = bool(env_var and os.environ.get(env_var))
        start = time.monotonic()
        try:
            api_key = self._resolve_test_api_key(encrypted_key, use_env=use_env)
            await litellm.acompletion(
                model=model_id,
                messages=[{"role": "user", "content": "ping"}],
                api_key=api_key,
                max_tokens=1,
            )
            latency_ms = int((time.monotonic() - start) * 1000)
            result = ConnectivityResult(ok=True, latency_ms=latency_ms)
        except InvalidToken:
            result = ConnectivityResult(
                ok=False,
                error="Stored API key could not be decrypted. Re-enter the API key for this model.",
            )
        except Exception as exc:
            result = ConnectivityResult(ok=False, error=str(exc))

        if self._audit_log:
            await self._audit_log.record(
                user_id="system",
                action="model_connectivity_tested",
                entity_type="model_registry",
                entity_id=model_pk,
                details={"ok": result.ok},
            )
        return result

    async def get_manifest(self) -> ManifestResult:
        chat: list[str] = []
        embedding: list[str] = []
        rerank: list[str] = []
        vision: list[str] = []
        for model_key, info in litellm.model_cost.items():
            if not isinstance(info, dict):
                continue
            provider = info.get("litellm_provider")
            mode = info.get("mode")
            name = f"{provider}/{model_key}" if provider else model_key
            if mode == "chat":
                chat.append(name)
            elif mode == "embedding":
                embedding.append(name)
            elif mode == "rerank":
                rerank.append(name)
            if info.get("supports_vision") is True:
                vision.append(name)
        return ManifestResult(
            chat=sorted(set(chat)),
            embedding=sorted(set(embedding)),
            rerank=sorted(set(rerank)),
            vision=sorted(set(vision)),
        )

    async def get_active_for_user_chat(self) -> list[ModelRegistryRow]:
        rows = await self._r.get_active_by_type(ModelType.llm)
        return [await self._annotate_row_async(row) for row in rows]

    async def get_active_vision_model(self) -> ModelRegistryRow | None:
        rows = await self._r.get_active_by_type(ModelType.vision)
        return await self._annotate_row_async(rows[0]) if rows else None

    async def resolve_connection(self, model_pk: str) -> ResolvedConnection:
        row = await self._r.get(model_pk)
        if not row:
            return ResolvedConnection(api_base=None, api_key=None)

        api_base = None
        if row.ollama_host_id and self._ollama_host_repo:
            host_row = await self._ollama_host_repo.get(row.ollama_host_id)
            if host_row:
                api_base = host_row.url

        api_key = None
        if row.api_key_id and self._llm_api_key_repo:
            key_row = await self._llm_api_key_repo.get(row.api_key_id)
            if key_row and key_row.value_encrypted:
                with contextlib.suppress(Exception):
                    api_key = self._secrets.decrypt(key_row.value_encrypted)

        return ResolvedConnection(api_base=api_base, api_key=api_key)

    async def get_by_litellm_id(self, litellm_model_id: str) -> ModelRegistryRow | None:
        rows = await self._r.list_all()
        for row in rows:
            lid = self._litellm_model_id(row.provider, row.model_id)
            if lid == litellm_model_id:
                return row
        return None

    async def resolve_litellm_model_id(self, model_id: str) -> str | None:
        """Given a litellm_model_id or bare model_id, return the full LiteLLM string.

        Looks up the registry row whose litellm_model_id matches, falling back to
        a direct match on the stored model_id field. Returns None if not found.
        """
        rows = await self._r.list_all()
        for row in rows:
            litellm_id = self._litellm_model_id(row.provider, row.model_id)
            if model_id in {litellm_id, row.model_id}:
                return litellm_id
        return None
