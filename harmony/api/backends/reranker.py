from __future__ import annotations

import dataclasses
import logging

import litellm
from kv_search import RerankerBackend, SearchHit

logger = logging.getLogger(__name__)


class HarmonyRerankerBackend(RerankerBackend):
    def __init__(self, *, model: str) -> None:
        self._model = model

    async def rerank(
        self,
        query: str,
        candidates: list[SearchHit],
        *,
        top_n: int,
    ) -> list[SearchHit]:
        docs = [h.metadata.get("content", h.path) for h in candidates]
        try:
            response = await litellm.arerank(
                model=self._model,
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
