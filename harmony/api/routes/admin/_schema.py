from __future__ import annotations

import pydantic
from fastapi import APIRouter

from harmony.indexer import IndexerConfigAdmin as IndexerConfig
from harmony.providers.web_crawler import CrawlerConfig

router = APIRouter()


@router.get("/crawler/schema")
async def get_crawler_schema() -> dict[str, pydantic.JsonValue]:
    """Get JSON Schema for crawler configuration."""
    return CrawlerConfig.model_json_schema()


@router.get("/indexer/schema")
async def get_indexer_schema() -> dict[str, pydantic.JsonValue]:
    """Get JSON Schema for indexer configuration."""
    return IndexerConfig.model_json_schema()
