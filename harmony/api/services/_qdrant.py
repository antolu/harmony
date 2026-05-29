from __future__ import annotations

import logging

import qdrant_client
import qdrant_client.models

from harmony.core import url_to_id as _url_to_id

logger = logging.getLogger(__name__)


class QdrantService:
    def __init__(self, *, host: str, collection: str) -> None:
        self._client = qdrant_client.AsyncQdrantClient(url=host)
        self._collection = collection

    async def ensure_collection(self) -> None:
        exists = await self._client.collection_exists(self._collection)
        if not exists:
            logger.info(
                "qdrant collection %s does not exist — will be created by the indexer on first run",
                self._collection,
            )

    async def upsert(self, vectors: list[tuple[str, list[float]]]) -> None:
        points = [
            qdrant_client.models.PointStruct(
                id=_url_to_id(url),
                vector=vector,
                payload={"path": url},
            )
            for url, vector in vectors
        ]
        await self._client.upsert(collection_name=self._collection, points=points)

    async def search(
        self,
        *,
        vector: list[float],
        top_n: int = 10,
        min_score: float = 0.35,
        allowlist: list[str] | None = None,
    ) -> list[tuple[str, float]]:
        query_filter = None
        if allowlist:
            query_filter = qdrant_client.models.Filter(
                must=[
                    qdrant_client.models.FieldCondition(
                        key="path",
                        match=qdrant_client.models.MatchAny(any=allowlist),
                    )
                ]
            )
        results = await self._client.search(
            collection_name=self._collection,
            query_vector=vector,
            limit=top_n,
            score_threshold=min_score,
            query_filter=query_filter,
        )
        return [(r.payload["path"], r.score) for r in results]

    async def is_empty(self) -> bool:
        info = await self._client.get_collection(self._collection)
        return (info.points_count or 0) == 0

    async def close(self) -> None:
        await self._client.close()
