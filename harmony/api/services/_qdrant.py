from __future__ import annotations

import logging
import typing

import pydantic
import qdrant_client
import qdrant_client.models

from harmony.core import url_to_id as _url_to_id

logger = logging.getLogger(__name__)


class QdrantService:
    def __init__(self, *, host: str, collection: str, vector_size: int = 512) -> None:
        self._client = qdrant_client.AsyncQdrantClient(url=host)
        self._collection = collection
        self._vector_size = vector_size

    async def ensure_collection(self) -> None:
        exists = await self._client.collection_exists(self._collection)
        if not exists:
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=qdrant_client.models.VectorParams(
                    size=self._vector_size,
                    distance=qdrant_client.models.Distance.COSINE,
                ),
            )
            logger.info("qdrant collection %s created", self._collection)

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
        results = await self._client.query_points(
            collection_name=self._collection,
            query=vector,
            limit=top_n,
            score_threshold=min_score,
            query_filter=query_filter,
        )
        return [
            (
                str(
                    typing.cast(dict[str, pydantic.JsonValue], r.payload).get(
                        "path", ""
                    )
                ),
                r.score,
            )
            for r in results.points
        ]

    async def collection_exists(self) -> bool:
        return await self._client.collection_exists(self._collection)

    async def get_collection_info(self) -> tuple[int, str | None]:
        """Return (vector_size, embedding_model) stored in the collection metadata."""
        info = await self._client.get_collection(self._collection)
        vectors = info.config.params.vectors
        size = (
            vectors.size
            if isinstance(vectors, qdrant_client.models.VectorParams)
            else 0
        )
        model = (info.config.metadata or {}).get("embedding_model")
        return size, model

    async def get_points_count(self) -> int:
        info = await self._client.get_collection(self._collection)
        return info.points_count or 0

    async def is_empty(self) -> bool:
        info = await self._client.get_collection(self._collection)
        return (info.points_count or 0) == 0

    @property
    def collection(self) -> str:
        return self._collection

    @property
    def client(self) -> qdrant_client.AsyncQdrantClient:
        return self._client

    async def delete_points(self, point_ids: list[int]) -> None:
        await self._client.delete(
            collection_name=self._collection,
            points_selector=point_ids,  # type: ignore[arg-type]  # qdrant_client expects a wider invariant list union
        )

    async def close(self) -> None:
        await self._client.close()
