from __future__ import annotations

import pytest

from harmony.api.backends._reranker import HarmonyRerankerBackend  # noqa: PLC2701
from harmony.api.backends._vector import HarmonyVectorBackend  # noqa: PLC2701
from harmony.api.services._llm import LLMService  # noqa: PLC2701


def test_blocks_external_model_when_flag_enabled() -> None:
    svc = LLMService()
    assert hasattr(svc, "_assert_data_residency"), (
        "LLMService must have _assert_data_residency method (Plan 04 adds this)"
    )
    with pytest.raises(RuntimeError):
        svc._assert_data_residency("gpt-4", data_residency_enabled=True)  # type: ignore[attr-defined]


def test_allows_ollama_when_flag_enabled() -> None:
    svc = LLMService()
    assert hasattr(svc, "_assert_data_residency"), (
        "LLMService must have _assert_data_residency method (Plan 04 adds this)"
    )
    svc._assert_data_residency("ollama/llama3", data_residency_enabled=True)  # type: ignore[attr-defined]


def test_allows_ollama_chat_when_flag_enabled() -> None:
    svc = LLMService()
    assert hasattr(svc, "_assert_data_residency"), (
        "LLMService must have _assert_data_residency method (Plan 04 adds this)"
    )
    svc._assert_data_residency("ollama_chat/llama3", data_residency_enabled=True)  # type: ignore[attr-defined]


def test_allows_external_when_flag_disabled() -> None:
    svc = LLMService()
    assert hasattr(svc, "_assert_data_residency"), (
        "LLMService must have _assert_data_residency method (Plan 04 adds this)"
    )
    svc._assert_data_residency("gpt-4", data_residency_enabled=False)  # type: ignore[attr-defined]


def test_vector_backend_blocks_embedding_when_flag_enabled() -> None:
    assert hasattr(HarmonyVectorBackend, "_check_data_residency"), (
        "HarmonyVectorBackend must have _check_data_residency method (Plan 04 adds this)"
    )


def test_reranker_backend_blocks_when_flag_enabled() -> None:
    assert hasattr(HarmonyRerankerBackend, "_check_data_residency"), (
        "HarmonyRerankerBackend must have _check_data_residency method (Plan 04 adds this)"
    )
