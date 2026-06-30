from __future__ import annotations

import pytest

PHASE_10_KEYS = {
    "document_cache_backend",
    "config_store",
    "job_executor",
    "vllm_completions_url",
    "vllm_embeddings_url",
    "vllm_reranker_url",
    "k8s_namespace",
    "k8s_job_image",
    "k8s_models_pvc_name",
    "k8s_data_pvc_name",
    "rate_limit_enabled",
    "rate_limit_per_user_per_min",
    "rate_limit_anon_per_ip_per_min",
    "rate_limit_search_per_min",
}


@pytest.mark.asyncio
async def test_defaults_with_no_env_and_no_db(monkeypatch: pytest.MonkeyPatch) -> None:
    from harmony.api.services.admin import ServiceConfigStore

    monkeypatch.delenv("JOB_EXECUTOR", raising=False)
    monkeypatch.delenv("CONFIG_STORE", raising=False)
    monkeypatch.delenv("DOCUMENT_CACHE_BACKEND", raising=False)

    store = ServiceConfigStore()
    store._repo = None

    assert await store.get("job_executor") == "subprocess"
    assert await store.get("config_store") == "filesystem"
    assert await store.get("document_cache_backend") == "memory"


@pytest.mark.asyncio
async def test_job_executor_env_beats_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from harmony.api.services.admin import ServiceConfigStore

    monkeypatch.setenv("JOB_EXECUTOR", "kubernetes")

    store = ServiceConfigStore()
    store._repo = None

    assert await store.get("job_executor") == "kubernetes"
    assert store.is_from_env("job_executor") is True


@pytest.mark.asyncio
async def test_vllm_completions_url_env_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    from harmony.api.services.admin import ServiceConfigStore

    monkeypatch.setenv("VLLM_COMPLETIONS_URL", "http://vllm:8000/v1")

    store = ServiceConfigStore()
    store._repo = None

    assert await store.get("vllm_completions_url") == "http://vllm:8000/v1"


def test_every_phase_10_key_has_env_map_entry() -> None:
    from harmony.api.services.admin import ServiceConfigStore

    missing = PHASE_10_KEYS - set(ServiceConfigStore._ENV_MAP)
    assert not missing, f"keys missing _ENV_MAP entry: {missing}"


def test_every_phase_10_key_has_default() -> None:
    from harmony.api.services.admin import ServiceConfigStore

    missing = PHASE_10_KEYS - set(ServiceConfigStore.DEFAULTS)
    assert not missing, f"keys missing DEFAULTS entry: {missing}"
