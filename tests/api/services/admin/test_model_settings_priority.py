from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_env_wins_over_db_for_embedding(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")
    from harmony.api.services.admin import model_settings as ms

    async def fake_db_get(key: str) -> str | None:
        return "ollama/other-model"

    monkeypatch.setattr(ms, "_db_get", fake_db_get)
    result = await ms.ModelSettingsStore().get_embedding_model()
    assert result == "openai/text-embedding-3-small"


@pytest.mark.asyncio
async def test_env_wins_over_db_for_reranker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RERANKER_MODEL", "openai/reranker")
    from harmony.api.services.admin import model_settings as ms

    async def fake_db_get(key: str) -> str | None:
        return "bge-reranker-v2-m3"

    monkeypatch.setattr(ms, "_db_get", fake_db_get)
    result = await ms.ModelSettingsStore().get_reranker_model()
    assert result == "openai/reranker"


@pytest.mark.asyncio
async def test_db_used_when_env_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    from harmony.api.services.admin import model_settings as ms

    async def fake_db_get(key: str) -> str | None:
        if key == "embedding_model":
            return "my-custom-model"
        return None

    monkeypatch.setattr(ms, "_db_get", fake_db_get)
    result = await ms.ModelSettingsStore().get_embedding_model()
    assert result == "my-custom-model"
