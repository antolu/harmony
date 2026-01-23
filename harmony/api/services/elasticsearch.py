from __future__ import annotations

import logging
import typing

from elasticsearch import AsyncElasticsearch

from harmony.api.config import settings

logger = logging.getLogger(__name__)


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

        response = await self.client.search(index=",".join(indices), body=search_query)
        return dict(response)

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

    async def search_multilingual(
        self,
        query: str,
        detected_language: str | None = None,
        min_results: int | None = None,
    ) -> dict[str, typing.Any]:
        """
        Search with language prioritization strategy.

        Strategy:
        1. If language detected, search that language index first
        2. If results < min_results, search other configured languages
        3. Merge and re-rank results by relevance score

        Args:
            query: Search query
            detected_language: Detected language of query (or None)
            min_results: Minimum results before searching other languages

        Returns:
            Combined search results with language metadata
        """
        if min_results is None:
            min_results = settings.es_config.mutable.min_results_before_fallback

        results: dict[str, typing.Any] = {
            "hits": {"hits": [], "total": {"value": 0}, "max_score": None}
        }
        searched_languages: list[str] = []

        if detected_language and detected_language in settings.es_config.languages:
            logger.info(f"Searching in detected language: {detected_language}")
            lang_results = await self.search(query, language=detected_language)
            results = dict(lang_results)
            searched_languages.append(detected_language)

            hits_count = lang_results["hits"]["total"]["value"]
            if hits_count >= min_results:
                results["_search_metadata"] = {
                    "searched_languages": searched_languages,
                    "strategy": "single_language",
                    "primary_language": detected_language,
                }
                return results

        other_languages = [
            lang
            for lang in settings.es_config.languages
            if lang not in searched_languages
        ]

        if other_languages:
            logger.info(f"Searching additional languages: {other_languages}")
            for lang in other_languages:
                lang_results = await self.search(query, language=lang)
                lang_results_dict = dict(lang_results)
                results["hits"]["hits"].extend(lang_results_dict["hits"]["hits"])
                results["hits"]["total"]["value"] += lang_results_dict["hits"]["total"][
                    "value"
                ]
                searched_languages.append(lang)

        results["hits"]["hits"].sort(key=lambda x: x["_score"], reverse=True)

        results["hits"]["hits"] = results["hits"]["hits"][
            : settings.search_results_size
        ]

        if results["hits"]["hits"]:
            results["hits"]["max_score"] = results["hits"]["hits"][0]["_score"]

        results["_search_metadata"] = {
            "searched_languages": searched_languages,
            "strategy": (
                "multilingual_fallback" if detected_language else "all_languages"
            ),
            "primary_language": detected_language,
        }

        return results


es_service = ElasticsearchService()
