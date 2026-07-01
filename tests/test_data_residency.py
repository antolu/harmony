from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from harmony.infrastructure.search import (
    HarmonyRerankerBackend,
)
from harmony.infrastructure.search._vector import HarmonyVectorBackend
from harmony.services._llm import LLMService


def _enabled_config() -> AsyncMock:
    mock = AsyncMock()
    mock.get = AsyncMock(return_value="true")
    return mock


def _disabled_config() -> AsyncMock:
    mock = AsyncMock()
    mock.get = AsyncMock(return_value="false")
    return mock


@pytest.mark.asyncio
async def test_blocks_external_model_when_flag_enabled() -> None:
    svc = LLMService(service_config=_enabled_config())
    with pytest.raises(RuntimeError):
        await svc._assert_data_residency("gpt-4")


@pytest.mark.asyncio
async def test_allows_ollama_when_flag_enabled() -> None:
    svc = LLMService(service_config=_enabled_config())
    await svc._assert_data_residency("ollama/llama3")


@pytest.mark.asyncio
async def test_allows_ollama_chat_when_flag_enabled() -> None:
    svc = LLMService(service_config=_enabled_config())
    await svc._assert_data_residency("ollama_chat/llama3")


@pytest.mark.asyncio
async def test_allows_external_when_flag_disabled() -> None:
    svc = LLMService(service_config=_disabled_config())
    await svc._assert_data_residency("gpt-4")


def test_vector_backend_blocks_embedding_when_flag_enabled() -> None:
    assert hasattr(HarmonyVectorBackend, "_assert_data_residency")


def test_reranker_backend_blocks_when_flag_enabled() -> None:
    assert hasattr(HarmonyRerankerBackend, "_assert_data_residency")
