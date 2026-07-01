from __future__ import annotations

import dataclasses
import typing
from datetime import datetime
from enum import StrEnum

import pydantic
from pydantic import BaseModel, Field

ConfigType = typing.Literal["crawler", "indexer"]


class ConfigEntry(BaseModel):
    name: str
    type: ConfigType
    created_at: datetime
    updated_at: datetime
    description: str | None = None


class ConfigListResponse(BaseModel):
    configs: list[ConfigEntry]


class ConfigSaveRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.\-]+$")
    config: dict[str, pydantic.JsonValue]
    description: str | None = None


class ConfigImportRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.\-]+$")
    description: str | None = None


class YamlExportResponse(BaseModel):
    name: str
    yaml_content: str


class ConfigRenameRequest(BaseModel):
    new_name: str = Field(
        ..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.\-]+$"
    )


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
    model_host_id: str | None
    api_key_id: str | None
    allowed_groups: list[str]
    cost_per_token: float | None
    enabled: bool
    created_at: datetime
    updated_at: datetime
    env_override: bool = False
    api_key_set: bool = False
    litellm_model_id: str = ""
    model_host: str | None = None
    api_key_name: str | None = None


@dataclasses.dataclass(frozen=True)
class ModelHostRow:
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
