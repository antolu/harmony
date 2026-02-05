from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from harmony.api.services.admin.service_config import service_config_store

router = APIRouter()


class IndexConfigResponse(BaseModel):
    index_base_name: str
    languages: list[str]


class IndexConfigRequest(BaseModel):
    index_base_name: str | None = None
    languages: list[str] | None = None


@router.get("", response_model=IndexConfigResponse)
async def get_index_config() -> IndexConfigResponse:
    """Get current Elasticsearch index configuration."""
    base_name = await service_config_store.get("es_index_base_name")
    languages_str = await service_config_store.get("es_languages")
    languages = [lang.strip() for lang in languages_str.split(",") if lang.strip()]

    return IndexConfigResponse(
        index_base_name=base_name,
        languages=languages,
    )


@router.put("")
async def update_index_config(config: IndexConfigRequest) -> dict[str, str]:
    """Update Elasticsearch index configuration."""
    if config.index_base_name is not None:
        await service_config_store.set(
            "es_index_base_name", config.index_base_name, validated=True
        )

    if config.languages is not None:
        languages_str = ",".join(config.languages)
        await service_config_store.set("es_languages", languages_str, validated=True)

    return {"status": "success", "message": "Index configuration updated"}
