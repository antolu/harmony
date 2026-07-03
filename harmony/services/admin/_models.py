from __future__ import annotations

import dataclasses
import typing
from datetime import datetime

from pydantic import BaseModel

__all__ = [
    "ConfigEntry",
    "ConfigType",
    "DomainExportItem",
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
