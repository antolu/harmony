from __future__ import annotations

import logging
import typing

from elasticsearch import AsyncElasticsearch

from harmony.api.config import settings

logger = logging.getLogger(__name__)


class ElasticsearchService:
    def __init__(self) -> None:
        self.client = AsyncElasticsearch([settings.es_config.host])
        self._host = settings.es_config.host

    async def reinitialize(self, host: str) -> None:
        """Reinitialize client with new host (called during app startup with service config)."""
        if host != self._host:
            logger.info(f"Reinitializing Elasticsearch client with host: {host}")
            await self.client.close()
            self.client = AsyncElasticsearch([host])
            self._host = host

    async def close(self) -> None:
        await self.client.close()

    async def health_check(self) -> bool:
        try:
            return await self.client.ping()
        except Exception:
            return False

    async def get_document(
        self, doc_id: str, language: str | None = None, index: str | None = None
    ) -> dict[str, typing.Any]:
        if index:
            idx = index
        elif language:
            idx = settings.es_config.get_index_name(language)
        else:
            idx = settings.es_config.get_all_indices()[0]

        response = await self.client.get(index=idx, id=doc_id)
        return response["_source"]


es_service = ElasticsearchService()
