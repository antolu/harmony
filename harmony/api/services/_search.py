from __future__ import annotations

import dataclasses
import logging

from kv_search import RerankerBackend, SearchEngine, SearchHit, VectorSearchBackend

from harmony.api.backends import HarmonyKeywordBackend, HarmonyKeywordQueries
from harmony.api.services._external_search import (
    ExternalSearchContext,
    ExternalSearchService,
)
from harmony.api.services._pipeline_config import PipelineConfig
from harmony.authz import AuthorizationContext

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class SearchContext:
    query: str
    language: str | None = None
    top_k: int | None = None
    authz_context: AuthorizationContext | None = None
    external_context: ExternalSearchContext | None = None
    sources: list[str] | None = None
    primary_query: str | None = None
    keyword_variants: list[str] | None = None


class SearchService:
    def __init__(
        self,
        *,
        keyword_backend: HarmonyKeywordBackend,
        vector_backend: VectorSearchBackend,
        reranker_backend: RerankerBackend | None = None,
        config: PipelineConfig,
        external_search_service: ExternalSearchService | None = None,
    ) -> None:
        self._engine = SearchEngine(
            keyword_backend=keyword_backend,
            vector_backend=vector_backend,
        )
        self._keyword_backend = keyword_backend
        self._vector_backend = vector_backend
        self._reranker_backend = reranker_backend
        self.config = config
        self._external_search_service = external_search_service

    async def search(self, ctx: SearchContext) -> list[SearchHit]:
        final_top_k = ctx.top_k if ctx.top_k is not None else self.config.search_top_k
        # The embedding/rerank text is the semantic query when provided (agentic
        # path), else the plain query (back-compat single-query callers).
        primary_query = ctx.primary_query or ctx.query
        # All keyword variants form the union allowlist; the keyword backend loops
        # over the list. Single-query callers default to [query].
        keyword_queries = ctx.keyword_variants or [ctx.query]

        acl_terms: list[str] = (
            ctx.authz_context.harmony_roles if ctx.authz_context else []
        )
        kw_queries = HarmonyKeywordQueries(
            queries=keyword_queries,
            language=ctx.language,
            acl_terms=acl_terms,
            sources=ctx.sources or [],
        )
        candidates = await self._keyword_backend.keyword_search(kw_queries)

        if self.config.vector_search_enabled:
            allowlist = [h.path for h in candidates[: self.config.keyword_candidates_n]]
            vec_hits = await self._vector_backend.vector_search(
                primary_query,
                top_n=self.config.vector_top_k,
                allowlist=allowlist,
            )
            if vec_hits:
                candidates = vec_hits

        ext_hits: list[SearchHit] = []
        if (
            self._external_search_service is not None
            and ctx.external_context is not None
        ):
            ext_hits = await self._external_search_service.fetch_external_results(
                primary_query,
                ctx.authz_context,
                request_toggle=ctx.external_context.request_toggle,
            )

        if self.config.reranker_enabled and self._reranker_backend is not None:
            merged = candidates + ext_hits if ext_hits else candidates
            candidates = await self._reranker_backend.rerank(
                primary_query,
                merged,
                top_n=final_top_k,
            )
        elif ext_hits:
            candidates += ext_hits

        return candidates[:final_top_k]
