from __future__ import annotations

import logging
import typing

from elasticsearch import AsyncElasticsearch

from harmony.api.config import settings

logger = logging.getLogger(__name__)


class ElasticsearchService:
    def __init__(self, host: str | None = None) -> None:
        self._host = host or settings.es_config.host
        self.client = AsyncElasticsearch([self._host])

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

    async def index_exists(self, name: str) -> bool:
        return await self.client.indices.exists(index=name)

    async def delete_index(self, name: str) -> None:
        await self.client.indices.delete(index=name)

    async def get_index_stats(self, name: str) -> dict[str, typing.Any]:
        return await self.client.indices.stats(index=name)

    async def list_indices(self, pattern: str) -> list[str]:
        try:
            result = await self.client.indices.get(index=pattern)
            return list(result.keys())
        except Exception as e:
            if "index_not_found_exception" in str(e):
                return []
            raise
