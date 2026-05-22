from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from kv_search import RerankerBackend, SearchEngine, SearchHit, VectorSearchBackend

from harmony.api.authz import AuthorizationContext
from harmony.api.backends import HarmonyKeywordBackend, HarmonyKeywordQueries
from harmony.api.services._pipeline_config import PipelineConfig

if TYPE_CHECKING:
    from harmony.api.services._external_search import (
        ExternalSearchContext,
        ExternalSearchService,
    )

logger = logging.getLogger(__name__)

# TODO: expose keyword_candidates_n, vector_top_k, search_top_k via admin frontend


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

    async def search(
        self,
        query: str,
        *,
        language: str | None = None,
        top_k: int | None = None,
        authz_context: AuthorizationContext | None = None,
        external_context: ExternalSearchContext | None = None,
    ) -> list[SearchHit]:
        final_top_k = top_k if top_k is not None else self.config.search_top_k

        acl_terms: list[str] = authz_context.harmony_roles if authz_context else []
        kw_queries = HarmonyKeywordQueries(
            queries=[query], language=language, acl_terms=acl_terms
        )
        candidates = await self._keyword_backend.keyword_search(kw_queries)

        if self.config.vector_search_enabled:
            allowlist = [h.path for h in candidates[: self.config.keyword_candidates_n]]
            vec_hits = await self._vector_backend.vector_search(
                query,
                top_n=self.config.vector_top_k,
                allowlist=allowlist,
            )
            if vec_hits:
                candidates = vec_hits

        ext_hits: list[SearchHit] = []
        if self._external_search_service is not None and external_context is not None:
            ext_hits = await self._external_search_service.fetch_external_results(
                query,
                authz_context,
                request_toggle=external_context.request_toggle,
            )

        if self.config.reranker_enabled and self._reranker_backend is not None:
            merged = candidates + ext_hits if ext_hits else candidates
            candidates = await self._reranker_backend.rerank(
                query,
                merged,
                top_n=final_top_k,
            )
        elif ext_hits:
            candidates += ext_hits

        return candidates[:final_top_k]
