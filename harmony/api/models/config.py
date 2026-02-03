from __future__ import annotations

import typing
from datetime import datetime

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
    config: dict[str, typing.Any]
    description: str | None = None


class ConfigImportRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.\-]+$")
    description: str | None = None


class YamlExportResponse(BaseModel):
    name: str
    yaml_content: str
