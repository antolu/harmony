from __future__ import annotations

import typing

from elasticsearch import AsyncElasticsearch

from harmony.api.config import settings


class ElasticsearchService:
    def __init__(self) -> None:
        self.client = AsyncElasticsearch([settings.es_config.host])

    async def close(self) -> None:
        await self.client.close()

    async def health_check(self) -> bool:
        try:
            return await self.client.ping()
        except Exception:
            return False

    async def search(
        self, query: str, language: str | None = None, index: str | None = None
    ) -> dict[str, typing.Any]:
        """
        Search across per-language indices.

        Args:
            query: Search query string
            language: Specific language to search (None = all languages)
            index: Override index name(s) (default from config)

        Returns:
            Elasticsearch search response
        """
        if index:
            indices = [index]
        elif language:
            indices = [settings.es_config.get_index_name(language)]
        else:
            indices = settings.es_config.get_all_indices()

        fields = [
            f"title^{settings.es_config.mutable.boost_title}",
            f"content^{settings.es_config.mutable.boost_content}",
        ]

        search_query = {
            "query": {
                "multi_match": {"query": query, "fields": fields, "type": "best_fields"}
            },
            "size": settings.search_results_size,
            "_source": ["url", "title", "content", "language", "domain", "path"],
            "highlight": {
                "fields": {"title": {}, "content": {}},
                "pre_tags": ["<mark>"],
                "post_tags": ["</mark>"],
            },
        }

        return await self.client.search(index=",".join(indices), body=search_query)

    async def get_document(
        self, doc_id: str, language: str | None = None, index: str | None = None
    ) -> dict[str, typing.Any]:
        """
        Get a single document by ID.

        Args:
            doc_id: Document ID
            language: Language for index routing
            index: Override index name (default from config)

        Returns:
            Document source
        """
        if index:
            idx = index
        elif language:
            idx = settings.es_config.get_index_name(language)
        else:
            idx = settings.es_config.get_all_indices()[0]

        response = await self.client.get(index=idx, id=doc_id)
        return response["_source"]


es_service = ElasticsearchService()
