from __future__ import annotations

from fastapi import APIRouter, Depends

from harmony.api.config import settings
from harmony.api.dependencies import get_service_config_store
from harmony.api.services.admin import ServiceConfigStore

router = APIRouter()


@router.get("/admin/infrastructure")
async def get_infrastructure_config(
    service_config: ServiceConfigStore = Depends(get_service_config_store),
) -> dict[str, str | None]:
    return {
        "elasticsearch_url": await service_config.get("elasticsearch_url"),
        "redis_url": await service_config.get("redis_url"),
        "es_index_base_name": await service_config.get("es_index_base_name"),
        "es_languages": await service_config.get("es_languages"),
        "es_state_index": await service_config.get("es_state_index"),
        "qdrant_host": settings.qdrant_host,
        "qdrant_collection": settings.qdrant_collection,
        "qdrant_vector_size": str(settings.qdrant_vector_size),  # type: ignore
        "embedding_batch_size": str(settings.embedding_batch_size),
    }
