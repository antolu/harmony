from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from harmony.services.admin import ConfigProvider

from ..._config import Settings
from ..._dependencies import (
    get_service_config_store,
    get_settings,
    require_role,
)

router = APIRouter()


@router.get("/admin/infrastructure")
async def get_infrastructure_config(
    service_config: ConfigProvider = Depends(get_service_config_store),
    settings: Settings = Depends(get_settings),
    _: None = Depends(require_role("admin")),
) -> dict[str, str | None]:
    return {
        "elasticsearch_url": await service_config.get("elasticsearch_url"),
        "redis_url": await service_config.get("redis_url"),
        "es_index_base_name": await service_config.get("es_index_base_name"),
        "es_languages": await service_config.get("es_languages"),
        "es_state_index": await service_config.get("es_state_index"),
        "qdrant_host": await service_config.get("qdrant_host"),
        "qdrant_collection": settings.qdrant_collection,
        "qdrant_vector_size": str(getattr(settings, "qdrant_vector_size", "")),
        "embedding_batch_size": await service_config.get(
            "pipeline_embedding_batch_size"
        ),
    }


class InfrastructureUpdate(BaseModel):
    elasticsearch_url: str | None = None
    qdrant_host: str | None = None


@router.patch("/admin/infrastructure")
async def update_infrastructure_config(
    update: InfrastructureUpdate,
    service_config: ConfigProvider = Depends(get_service_config_store),
    _: None = Depends(require_role("admin")),
) -> dict[str, str]:
    if update.elasticsearch_url is not None:
        await service_config.set("elasticsearch_url", update.elasticsearch_url)
    if update.qdrant_host is not None:
        await service_config.set("qdrant_host", update.qdrant_host)
    return {
        "elasticsearch_url": await service_config.get("elasticsearch_url") or "",
        "qdrant_host": await service_config.get("qdrant_host") or "",
    }
