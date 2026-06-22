from __future__ import annotations

import dataclasses
from datetime import datetime
from enum import StrEnum


class ModelType(StrEnum):
    llm = "llm"
    embedding = "embedding"
    reranker = "reranker"
    vision = "vision"


@dataclasses.dataclass(frozen=True)
class ModelRegistryRow:
    id: str
    name: str
    provider: str
    model_id: str
    model_type: str
    ollama_host_id: str | None
    api_key_id: str | None
    allowed_groups: list[str]
    cost_per_token: float | None
    enabled: bool
    created_at: datetime
    updated_at: datetime
    env_override: bool = False
    api_key_set: bool = False
    litellm_model_id: str = ""
    ollama_host: str | None = None
    api_key_name: str | None = None


@dataclasses.dataclass(frozen=True)
class OllamaHostRow:
    id: str
    name: str
    url: str
    host_type: str
    created_at: datetime
    updated_at: datetime
    model_count: int = 0


@dataclasses.dataclass(frozen=True)
class LLMApiKeyRow:
    id: str
    name: str
    value_encrypted: str | None
    created_at: datetime
    updated_at: datetime
    value_set: bool = False
    model_count: int = 0
