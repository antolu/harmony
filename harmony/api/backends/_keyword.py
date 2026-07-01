from __future__ import annotations

import dataclasses
import logging

import elasticsearch
import structlog
from kv_search import KeywordQueries, KeywordSearchBackend, SearchHit

from harmony.api.services.admin import ConfigProvider

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class HarmonyKeywordQueries(KeywordQueries):
    language: str | None = None
    acl_terms: list[str] = dataclasses.field(default_factory=list)
    sources: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(frozen=True)
class KeywordBackendConfig:
    host: str
    index_base_name: str
    languages: list[str]
    size: int = 50


class HarmonyKeywordBackend(KeywordSearchBackend):
    def __init__(
        self, config: KeywordBackendConfig, service_config: ConfigProvider
    ) -> None:
        self._client = elasticsearch.AsyncElasticsearch([config.host])
        self._index_base_name = config.index_base_name
        self._languages = config.languages
        self._size = config.size
        self._service_config = service_config

    def _index_for(self, language: str) -> str:
        return f"{self._index_base_name}-{language}"

    async def _search_index(
        self,
        queries: list[str],
        index: str,
        acl_terms: list[str],
        sources: list[str],
    ) -> list[SearchHit]:
        if not acl_terms:
            return []

        hits: list[SearchHit] = []
        seen: set[str] = set()
        boost_title = float(await self._service_config.get("es_boost_title"))
        boost_content = float(await self._service_config.get("es_boost_content"))
        for q in queries:
            try:
                response = await self._client.search(
                    index=index,
                    query={
                        "bool": {
                            "must": [
                                {
                                    "multi_match": {
                                        "query": q,
                                        "fields": [
                                            f"title^{boost_title}",
                                            f"content^{boost_content}",
                                        ],
                                        "type": "best_fields",
                                    }
                                }
                            ],
                            "filter": [
                                {"terms": {"acl.allowed_roles": acl_terms}},
                                {"exists": {"field": "acl.policy_version"}},
                                *(
                                    [{"terms": {"source_name": sources}}]
                                    if sources
                                    else []
                                ),
                            ],
                        }
                    },
                    size=self._size,
                    source={
                        "includes": [
                            "url",
                            "title",
                            "content",
                            "language",
                            "domain",
                            "source_name",
                        ]
                    },
                )
            except Exception:
                logger.exception(
                    "ES keyword search failed for query %r on index %s", q, index
                )
                continue

            for item in response.get("hits", {}).get("hits", []):
                source = item.get("_source", {})
                url = source.get("url")
                if url and url not in seen:
                    seen.add(url)
                    hits.append(
                        SearchHit(
                            path=url,
                            score=float(item.get("_score") or 0.0),
                            metadata={
                                k: v
                                for k, v in source.items()
                                if k != "url"
                                and isinstance(v, str | int | float | bool)
                            },
                        )
                    )

        try:
            count_response = await self._client.count(
                index=index,
                query={
                    "bool": {"must_not": {"exists": {"field": "acl.policy_version"}}}
                },
            )
            missing_count = count_response.get("count", 0)
            if missing_count > 0:
                structlog.get_logger().warning(
                    "acl_missing_docs_detected",
                    index=index,
                    count=missing_count,
                )
        except Exception:
            logger.exception("Failed to count missing-ACL docs on index %s", index)

        return hits

    async def keyword_search(self, queries: KeywordQueries) -> list[SearchHit]:
        language: str | None = None
        acl_terms: list[str] = []
        sources: list[str] = []
        if isinstance(queries, HarmonyKeywordQueries):
            language = queries.language
            acl_terms = queries.acl_terms
            sources = queries.sources

        if not acl_terms:
            return []

        min_results = int(
            await self._service_config.get("es_min_results_before_fallback")
        )

        if language and language in self._languages:
            hits = await self._search_index(
                queries.queries, self._index_for(language), acl_terms, sources
            )
            if len(hits) >= min_results:
                return hits
            other_langs = [lang for lang in self._languages if lang != language]
        else:
            hits = []
            other_langs = self._languages

        seen_paths = {h.path for h in hits}
        for lang in other_langs:
            lang_hits = await self._search_index(
                queries.queries, self._index_for(lang), acl_terms, sources
            )
            for h in lang_hits:
                if h.path not in seen_paths:
                    seen_paths.add(h.path)
                    hits.append(h)

        return hits

    async def close(self) -> None:
        await self._client.close()
