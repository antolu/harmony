from __future__ import annotations

import dataclasses
import typing

import structlog

from harmony.clients import ElasticsearchService, QdrantService

if typing.TYPE_CHECKING:
    from harmony.services.admin import ServiceConfigStore

    from .._config import Settings

logger = structlog.get_logger(__name__)


@dataclasses.dataclass(frozen=True)
class StorageServices:
    es_service: ElasticsearchService
    qdrant_service: QdrantService | None


async def init_storage_services(
    service_config: ServiceConfigStore, settings: Settings
) -> StorageServices:
    es_url = await service_config.get("elasticsearch_url")
    es_service = ElasticsearchService(host=es_url, es_config=settings.es_config)
    if await es_service.health_check():
        logger.info(f"Connected to Elasticsearch at {es_url}")
    else:
        logger.error(f"Failed to connect to Elasticsearch at {es_url}")

    qdrant_service = await QdrantService.create(
        service_config=service_config, collection=settings.qdrant_collection
    )
    return StorageServices(es_service=es_service, qdrant_service=qdrant_service)
