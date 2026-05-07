from __future__ import annotations

import dataclasses
import logging

import elasticsearch
from kv_search import KeywordQueries, KeywordSearchBackend, SearchHit

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class HarmonyKeywordQueries(KeywordQueries):
    language: str | None = None


class HarmonyKeywordBackend(KeywordSearchBackend):
    def __init__(  # noqa: PLR0913
        self,
        *,
        host: str,
        index_base_name: str,
        languages: list[str],
        min_results_before_fallback: int = 5,
        boost_title: float = 2.0,
        boost_content: float = 1.0,
        size: int = 50,
    ) -> None:
        self._client = elasticsearch.AsyncElasticsearch([host])
        self._index_base_name = index_base_name
        self._languages = languages
        self._min_results_before_fallback = min_results_before_fallback
        self._boost_title = boost_title
        self._boost_content = boost_content
        self._size = size

    def _index_for(self, language: str) -> str:
        return f"{self._index_base_name}-{language}"

    async def _search_index(self, queries: list[str], index: str) -> list[SearchHit]:
        hits: list[SearchHit] = []
        seen: set[str] = set()
        for q in queries:
            try:
                response = await self._client.search(
                    index=index,
                    query={
                        "multi_match": {
                            "query": q,
                            "fields": [
                                f"title^{self._boost_title}",
                                f"content^{self._boost_content}",
                            ],
                            "type": "best_fields",
                        }
                    },
                    size=self._size,
                    source=["url", "title", "content", "language", "domain"],
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
        return hits

    async def keyword_search(self, queries: KeywordQueries) -> list[SearchHit]:
        language: str | None = None
        if isinstance(queries, HarmonyKeywordQueries):
            language = queries.language

        if language and language in self._languages:
            hits = await self._search_index(queries.queries, self._index_for(language))
            if len(hits) >= self._min_results_before_fallback:
                return hits
            other_langs = [lang for lang in self._languages if lang != language]
        else:
            hits = []
            other_langs = self._languages

        seen_paths = {h.path for h in hits}
        for lang in other_langs:
            lang_hits = await self._search_index(queries.queries, self._index_for(lang))
            for h in lang_hits:
                if h.path not in seen_paths:
                    seen_paths.add(h.path)
                    hits.append(h)

        return hits

    async def close(self) -> None:
        await self._client.close()
