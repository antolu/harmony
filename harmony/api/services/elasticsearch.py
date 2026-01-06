from __future__ import annotations

from typing import Any

from elasticsearch import AsyncElasticsearch

from harmony.api.config import settings


class ElasticsearchService:
    def __init__(self) -> None:
        self.client = AsyncElasticsearch([settings.es_host])

    async def close(self) -> None:
        await self.client.close()

    async def health_check(self) -> bool:
        try:
            return await self.client.ping()
        except Exception:
            return False

    async def search(
        self, query: str, index: str | None = None, language: str | None = None
    ) -> dict[str, Any]:
        """
        Search documents using multi-match query with language-aware field boosting.

        Args:
            query: Search query string
            index: Elasticsearch index name (default from settings)
            language: Language code (en, fr) for field boosting

        Returns:
            Elasticsearch search response
        """
        index = index or settings.es_index

        # Build field list with boosting
        fields = ["title^2", "content"]

        if language:
            # Boost language-specific fields more
            fields.extend([f"title.{language}^3", f"content.{language}^1.5"])
        else:
            # Include both language fields with standard boost
            fields.extend([
                "title.en^2.5",
                "title.fr^2.5",
                "content.en^1.2",
                "content.fr^1.2",
            ])

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

        return await self.client.search(index=index, body=search_query)

    async def get_document(
        self, doc_id: str, index: str | None = None
    ) -> dict[str, Any]:
        """
        Get a single document by ID.

        Args:
            doc_id: Document ID
            index: Elasticsearch index name

        Returns:
            Document source
        """
        index = index or settings.es_index
        response = await self.client.get(index=index, id=doc_id)
        return response["_source"]


# Global instance
es_service = ElasticsearchService()
