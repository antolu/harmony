from __future__ import annotations

import logging

import litellm
from kv_search import SearchHit, VectorSearchBackend

from harmony.api.services.qdrant import QdrantService

logger = logging.getLogger(__name__)


class HarmonyVectorBackend(VectorSearchBackend):
    def __init__(self, *, qdrant_service: QdrantService, embedding_model: str) -> None:
        self._qdrant = qdrant_service
        self._embedding_model = embedding_model

    async def vector_search(
        self,
        query: str,
        *,
        top_n: int = 10,
        min_score: float = 0.35,
        allowlist: list[str] | None = None,
    ) -> list[SearchHit]:
        try:
            response = await litellm.aembedding(
                model=self._embedding_model, input=[query]
            )
            vector: list[float] = response.data[0].embedding
        except Exception:
            logger.exception("embedding failed for query %r", query)
            return []

        results = await self._qdrant.search(
            vector=vector,
            top_n=top_n,
            min_score=min_score,
            allowlist=allowlist,
        )
        return [SearchHit(path=path, score=score) for path, score in results]
