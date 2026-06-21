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
    api_key_encrypted: str | None
    allowed_groups: list[str]
    cost_per_token: float | None
    enabled: bool
    ollama_host: str | None
    created_at: datetime
    updated_at: datetime
    env_override: bool = False
    api_key_set: bool = False
    litellm_model_id: str = ""
