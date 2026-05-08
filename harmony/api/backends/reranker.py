from __future__ import annotations

import dataclasses
import logging

import litellm
from kv_search import RerankerBackend, SearchHit

from harmony.api.services.admin import model_settings_store

logger = logging.getLogger(__name__)


class HarmonyRerankerBackend(RerankerBackend):
    async def rerank(
        self,
        query: str,
        candidates: list[SearchHit],
        *,
        top_n: int,
    ) -> list[SearchHit]:
        reranker_model = await model_settings_store.get_reranker_model()
        docs = [h.metadata.get("content", h.path) for h in candidates]
        try:
            response = await litellm.arerank(
                model=reranker_model,
                query=query,
                documents=docs,
                top_n=top_n,
            )
        except Exception:
            logger.exception(
                "reranker failed for query %r, returning candidates as-is", query
            )
            return candidates[:top_n]

        return [
            dataclasses.replace(candidates[r.index], score=r.relevance_score)
            for r in response.results
        ]
