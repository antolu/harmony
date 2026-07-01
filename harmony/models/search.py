from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Source(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = ""
    url: str = ""
    domain: str = ""
    content: str = ""
    snippet: str = ""
    score: float = 0.0
    source_type: str = "indexed"
