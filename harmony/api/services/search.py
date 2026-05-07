from __future__ import annotations

import logging

from kv_search import SearchEngine, SearchHit

from harmony.api.backends.keyword import HarmonyKeywordBackend, HarmonyKeywordQueries
from harmony.api.backends.vector import HarmonyVectorBackend

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(
        self,
        *,
        keyword_backend: HarmonyKeywordBackend,
        vector_backend: HarmonyVectorBackend,
    ) -> None:
        self._engine = SearchEngine(
            keyword_backend=keyword_backend,
            vector_backend=vector_backend,
        )

    async def search(
        self,
        query: str,
        *,
        language: str | None = None,
        semantic: bool = False,
        top_k: int = 10,
    ) -> list[SearchHit]:
        if semantic:
            msg = "Semantic search is not yet implemented"
            raise NotImplementedError(msg)

        session = self._engine.new_session()

        kw_queries = HarmonyKeywordQueries(queries=[query], language=language)
        kw_hits = await self._engine.keyword_search(session, kw_queries)

        if len(session.allowlist) > top_k:
            session.set_allowlist(session.allowlist[:top_k])

        vec_hits = await self._engine.vector_search(session, query, top_n=top_k)

        return vec_hits if vec_hits else kw_hits[:top_k]


# TODO: refactor to use request.app.state.search_service via FastAPI Depends
search_service: SearchService | None = None
