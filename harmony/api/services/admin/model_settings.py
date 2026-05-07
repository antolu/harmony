from __future__ import annotations

from harmony.api.config import settings as app_settings
from harmony.db.repositories import ServiceConfigRepo

_DEFAULTS: dict[str, str] = {
    "embedding_provider": "ollama",
    "embedding_model": app_settings.embedding_model,
    "reranker_provider": "ollama",
    "reranker_model": "ollama/bge-reranker-v2-m3",
    "llm_provider": "litellm",
    "llm_model": app_settings.llm_model,
    "embedding_model_changed_since_last_embed": "false",
}

_ENV_VALUES: dict[str, str | None] = {
    "embedding_model": app_settings.embedding_model
    if app_settings.embedding_model != "ollama/qwen3-embedding:0.6b"
    else None,
    "llm_model": app_settings.llm_model
    if app_settings.llm_model != "gemini/gemini-3-flash-preview"
    else None,
}


class ModelSettingsStore:
    async def get(self, key: str) -> str:
        env_val = _ENV_VALUES.get(key)
        if env_val:
            return env_val

        from harmony.db.connection import get_async_pool  # noqa: PLC0415

        pool = await get_async_pool()
        async with pool.connection() as conn:
            repo = ServiceConfigRepo(conn)
            row = await repo.get(key)
            if row and row.get("is_configured"):
                return row["value"]
        return _DEFAULTS[key]

    async def set(self, key: str, value: str) -> None:
        from harmony.db.connection import get_async_pool  # noqa: PLC0415

        pool = await get_async_pool()
        async with pool.connection() as conn:
            repo = ServiceConfigRepo(conn)
            await repo.upsert(key, value, None, validated=True)

    async def get_all(self) -> dict[str, str]:
        return {k: await self.get(k) for k in _DEFAULTS}


model_settings_store = ModelSettingsStore()
