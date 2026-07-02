from __future__ import annotations

import dataclasses
import typing
from datetime import datetime

import pydantic
from pydantic import BaseModel, Field

from harmony.db.repositories._llm_api_keys import LLMApiKeyRow
from harmony.db.repositories._model_hosts import ModelHostRow
from harmony.db.repositories._models import ModelRegistryRow, ModelType

__all__ = [
    "ConfigEntry",
    "ConfigImportRequest",
    "ConfigListResponse",
    "ConfigRenameRequest",
    "ConfigSaveRequest",
    "ConfigType",
    "DomainExportItem",
    "LLMApiKeyRow",
    "ModelHostRow",
    "ModelRegistryRow",
    "ModelType",
    "YamlExportResponse",
]

ConfigType = typing.Literal["crawler", "indexer"]


@dataclasses.dataclass
class DomainExportItem:
    domain: str
    doc_count: int


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
