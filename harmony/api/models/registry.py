from __future__ import annotations

import typing
from enum import StrEnum


class ModelType(StrEnum):
    llm = "llm"
    embedding = "embedding"
    reranker = "reranker"
    vision = "vision"


class ModelRegistryRow(typing.TypedDict, total=False):
    id: str
    name: str
    provider: str
    model_id: str
    model_type: str
    api_key_encrypted: str | None
    allowed_groups: list[str]
    cost_per_token: float | None
    enabled: bool
    ollama_host: str | None
    created_at: typing.Any
    updated_at: typing.Any
    env_override: bool
    api_key_set: bool
    litellm_model_id: str
