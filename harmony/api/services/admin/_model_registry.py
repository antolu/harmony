from __future__ import annotations

import logging
import os
import time
import typing
from pathlib import Path

import litellm
import psycopg_pool

from harmony.api.observability._secret_service import SecretValueService
from harmony.api.services.admin._audit_log import AuditLogService
from harmony.db.repositories import ModelRegistryRepo

logger = logging.getLogger(__name__)

_ENV_OVERRIDES: dict[str, str] = {
    "llm": "LLM_MODEL",
    "embedding": "EMBEDDING_MODEL",
    "reranker": "RERANKER_MODEL",
}

_MANIFEST_PATH = (
    Path(__file__).parent.parent.parent.parent / "static" / "model_manifest.json"
)


class ModelRegistryService:
    def __init__(self) -> None:
        self._repo: ModelRegistryRepo | None = None
        self._secret_svc: SecretValueService | None = None
        self._audit_log: AuditLogService | None = None

    async def initialize(
        self,
        pool: psycopg_pool.AsyncConnectionPool,
        audit_log_service: AuditLogService,
        secret_service: SecretValueService,
    ) -> None:
        self._repo = ModelRegistryRepo(pool)
        self._audit_log = audit_log_service
        self._secret_svc = secret_service

    def _annotate_row(self, row: dict[str, typing.Any]) -> dict[str, typing.Any]:
        model_type = row.get("model_type", "")
        env_var = _ENV_OVERRIDES.get(model_type)
        row["env_override"] = bool(env_var and os.environ.get(env_var))
        row["api_key_set"] = bool(row.pop("api_key_encrypted", None))
        return row

    async def list(self) -> list[dict[str, typing.Any]]:
        assert self._repo is not None
        rows = await self._repo.list()
        return [self._annotate_row(dict(row)) for row in rows]

    async def get(self, model_pk: str) -> dict[str, typing.Any] | None:
        assert self._repo is not None
        row = await self._repo.get(model_pk)
        if row is None:
            return None
        row = dict(row)
        row.pop("api_key_encrypted", None)
        return self._annotate_row(row)

    async def create(  # noqa: PLR0913
        self,
        name: str,
        provider: str,
        model_id: str,
        model_type: str,
        api_key: str | None,
        cost_per_token: float | None,
        *,
        enabled: bool,
        ollama_host: str | None,
        created_by: str,
    ) -> dict[str, typing.Any]:
        assert self._repo is not None
        assert self._secret_svc is not None
        encrypted = self._secret_svc.encrypt(api_key) if api_key else None
        row = await self._repo.create(
            name=name,
            provider=provider,
            model_id=model_id,
            model_type=model_type,
            api_key_encrypted=encrypted,
            cost_per_token=cost_per_token,
            enabled=enabled,
            ollama_host=ollama_host,
        )
        if self._audit_log:
            await self._audit_log.record(
                user_id=created_by,
                action="model_created",
                entity_type="model_registry",
                entity_id=str(row.get("id")),
                details={"name": name, "provider": provider, "model_type": model_type},
            )
        return self._annotate_row(dict(row))

    async def update(
        self, model_pk: str, fields: dict[str, typing.Any], updated_by: str
    ) -> dict[str, typing.Any] | None:
        assert self._repo is not None
        assert self._secret_svc is not None
        fields = dict(fields)
        if "api_key" in fields:
            raw_key = fields.pop("api_key")
            fields["api_key_encrypted"] = (
                self._secret_svc.encrypt(raw_key) if raw_key else None
            )
        changed_fields = [k for k in fields if k != "api_key_encrypted"]
        row = await self._repo.update(model_pk, fields)
        if row is None:
            return None
        if self._audit_log:
            await self._audit_log.record(
                user_id=updated_by,
                action="model_updated",
                entity_type="model_registry",
                entity_id=model_pk,
                details={"fields_changed": changed_fields},
            )
        return self._annotate_row(dict(row))

    async def delete(self, model_pk: str, deleted_by: str) -> bool:
        assert self._repo is not None
        result = await self._repo.delete(model_pk)
        if result and self._audit_log:
            await self._audit_log.record(
                user_id=deleted_by,
                action="model_deleted",
                entity_type="model_registry",
                entity_id=model_pk,
                details={},
            )
        return result

    async def test_connectivity(self, model_pk: str) -> dict[str, typing.Any]:
        assert self._repo is not None
        assert self._secret_svc is not None
        row = await self._repo.get(model_pk)
        if row is None:
            return {"ok": False, "error": "Model not found"}

        model_id = row.get("model_id", "")
        model_type = row.get("model_type", "")
        encrypted_key = row.get("api_key_encrypted")

        env_var = _ENV_OVERRIDES.get(model_type)
        if env_var and os.environ.get(env_var):
            api_key = None
        elif encrypted_key:
            api_key = self._secret_svc.decrypt(encrypted_key)
        else:
            api_key = None

        start = time.monotonic()
        try:
            await litellm.acompletion(
                model=model_id,
                messages=[{"role": "user", "content": "ping"}],
                api_key=api_key,
                max_tokens=1,
            )
            latency_ms = int((time.monotonic() - start) * 1000)
            result: dict[str, typing.Any] = {"ok": True, "latency_ms": latency_ms}
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}

        if self._audit_log:
            await self._audit_log.record(
                user_id="system",
                action="model_connectivity_tested",
                entity_type="model_registry",
                entity_id=model_pk,
                details={"ok": result.get("ok")},
            )
        return result

    async def get_manifest(self) -> dict[str, typing.Any]:
        import litellm  # noqa: PLC0415

        chat: list[str] = []
        embedding: list[str] = []
        rerank: list[str] = []
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
        return {
            "chat": sorted(set(chat)),
            "embedding": sorted(set(embedding)),
            "rerank": sorted(set(rerank)),
        }

    async def get_active_for_user_chat(self) -> list[dict[str, typing.Any]]:  # type: ignore[valid-type]
        assert self._repo is not None
        rows: list[dict[str, typing.Any]] = await self._repo.get_active_by_type("llm")  # type: ignore[valid-type,assignment]
        return [self._annotate_row(dict(row)) for row in rows]
