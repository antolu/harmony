from __future__ import annotations

import pytest

from harmony.db.models import ModelType
from harmony.services.admin import ModelRegistryService


@pytest.mark.parametrize(
    ("provider", "model_id", "model_type", "expected"),
    [
        ("ollama", "qwen3:8b", ModelType.llm, "ollama_chat/qwen3:8b"),
        (
            "ollama",
            "qwen3-embedding:0.6b",
            ModelType.embedding,
            "ollama/qwen3-embedding:0.6b",
        ),
        (
            "ollama",
            "bge-reranker-v2-m3",
            ModelType.reranker,
            "ollama/bge-reranker-v2-m3",
        ),
        (
            "hosted_vllm",
            "Qwen/Qwen3.5-9B",
            ModelType.llm,
            "hosted_vllm/Qwen/Qwen3.5-9B",
        ),
        ("openai", "gpt-4", ModelType.llm, "openai/gpt-4"),
        ("anthropic", "claude-3-5-sonnet", None, "anthropic/claude-3-5-sonnet"),
    ],
)
def test_litellm_model_id_builds_expected_provider_prefix(
    provider: str, model_id: str, model_type: ModelType | None, expected: str
) -> None:
    result = ModelRegistryService._litellm_model_id(provider, model_id, model_type)
    assert result == expected


def test_litellm_model_id_keeps_internal_slashes_in_vllm_model_id() -> None:
    """A vLLM model id can contain a HF org/model path with internal slashes —
    only the leading provider prefix is meaningful, the rest must pass through."""
    result = ModelRegistryService._litellm_model_id(
        "hosted_vllm", "Qwen/Qwen3.5-9B", ModelType.llm
    )
    assert result == "hosted_vllm/Qwen/Qwen3.5-9B"
