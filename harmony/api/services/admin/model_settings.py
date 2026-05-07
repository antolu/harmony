from __future__ import annotations

import dataclasses
from typing import Literal

from harmony.api.config import settings as app_settings
from harmony.db.connection import get_async_pool
from harmony.db.repositories import ServiceConfigRepo

Provider = Literal["ollama", "litellm"]

_DEFAULT_EMBEDDING_MODEL = "ollama/qwen3-embedding:0.6b"
_DEFAULT_RERANKER_MODEL = "ollama/bge-reranker-v2-m3"
_DEFAULT_LLM_MODEL = "gemini/gemini-3-flash-preview"


@dataclasses.dataclass
class ModelSettings:
    embedding_provider: Provider
    embedding_model: str
    reranker_provider: Provider
    reranker_model: str
    llm_provider: Provider
    llm_model: str
    embedding_model_changed_since_last_embed: bool


async def _db_get(key: str) -> str | None:
    pool = await get_async_pool()
    repo = ServiceConfigRepo(pool)
    row = await repo.get(key)
    if row and row.get("is_configured"):
        return row["value"]
    return None


async def _db_save(key: str, value: str) -> None:
    pool = await get_async_pool()
    repo = ServiceConfigRepo(pool)
    await repo.upsert(key, value, None, validated=True)


def _as_provider(value: str) -> Provider:
    if value in {"ollama", "litellm"}:
        return value  # type: ignore[return-value]
    return "litellm"


class ModelSettingsStore:
    async def get_embedding_model(self) -> str:
        env = app_settings.embedding_model
        if env != _DEFAULT_EMBEDDING_MODEL:
            return env
        return (await _db_get("embedding_model")) or _DEFAULT_EMBEDDING_MODEL

    async def get_reranker_model(self) -> str:
        return (await _db_get("reranker_model")) or _DEFAULT_RERANKER_MODEL

    async def get_llm_model(self) -> str:
        env = app_settings.llm_model
        if env != _DEFAULT_LLM_MODEL:
            return env
        return (await _db_get("llm_model")) or _DEFAULT_LLM_MODEL

    async def get_embedding_provider(self) -> Provider:
        return _as_provider((await _db_get("embedding_provider")) or "ollama")

    async def get_reranker_provider(self) -> Provider:
        return _as_provider((await _db_get("reranker_provider")) or "ollama")

    async def get_llm_provider(self) -> Provider:
        return _as_provider((await _db_get("llm_provider")) or "litellm")

    async def get_embedding_changed(self) -> bool:
        return (await _db_get("embedding_model_changed_since_last_embed")) == "true"

    async def save_embedding_model(self, value: str) -> None:
        await _db_save("embedding_model", value)

    async def save_reranker_model(self, value: str) -> None:
        await _db_save("reranker_model", value)

    async def save_llm_model(self, value: str) -> None:
        await _db_save("llm_model", value)

    async def save_embedding_provider(self, value: Provider) -> None:
        await _db_save("embedding_provider", value)

    async def save_reranker_provider(self, value: Provider) -> None:
        await _db_save("reranker_provider", value)

    async def save_llm_provider(self, value: Provider) -> None:
        await _db_save("llm_provider", value)

    async def mark_embedding_changed(self) -> None:
        await _db_save("embedding_model_changed_since_last_embed", "true")

    async def clear_embedding_changed(self) -> None:
        await _db_save("embedding_model_changed_since_last_embed", "false")

    async def get_all(self) -> ModelSettings:
        return ModelSettings(
            embedding_provider=await self.get_embedding_provider(),
            embedding_model=await self.get_embedding_model(),
            reranker_provider=await self.get_reranker_provider(),
            reranker_model=await self.get_reranker_model(),
            llm_provider=await self.get_llm_provider(),
            llm_model=await self.get_llm_model(),
            embedding_model_changed_since_last_embed=await self.get_embedding_changed(),
        )


model_settings_store = ModelSettingsStore()
