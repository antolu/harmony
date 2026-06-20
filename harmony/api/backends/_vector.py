from __future__ import annotations

import logging
import typing

import litellm
import structlog.contextvars
from kv_search import SearchHit, VectorSearchBackend

from harmony.api.services import QdrantService
from harmony.api.services.admin import ModelSettingsStore
from harmony.api.services.admin._service_config import ServiceConfigStore

logger = logging.getLogger(__name__)


class HarmonyVectorBackend(VectorSearchBackend):
    _LOCAL_PREFIXES: typing.ClassVar[tuple[str, ...]] = ("ollama/", "ollama_chat/")

    def __init__(
        self,
        *,
        qdrant_service: QdrantService | None,
        service_config: ServiceConfigStore,
        model_settings_store: ModelSettingsStore,
    ) -> None:
        self._qdrant = qdrant_service
        self._service_config = service_config
        self._model_settings_store = model_settings_store

    async def _assert_data_residency(self, model: str) -> None:
        flag = await self._service_config.get("data_residency_mode")
        if (
            flag
            and flag.lower() in {"true", "1", "yes"}
            and not any(model.startswith(p) for p in self._LOCAL_PREFIXES)
        ):
            msg = f"Data residency mode is enabled — external provider '{model}' is not permitted."
            raise RuntimeError(msg)

    async def vector_search(
        self,
        query: str,
        *,
        top_n: int = 10,
        min_score: float = 0.35,
        allowlist: list[str] | None = None,
    ) -> list[SearchHit]:
        if self._qdrant is None:
            return []

        embedding_model = await self._model_settings_store.get_embedding_model()
        await self._assert_data_residency(embedding_model)
        embedding_args: dict[str, object] = {
            "model": embedding_model,
            "input": [query],
            "metadata": {
                "trace_id": structlog.contextvars.get_contextvars().get("trace_id", ""),
                "agent_step": "embedding",
            },
        }
        if any(embedding_model.startswith(p) for p in self._LOCAL_PREFIXES):
            ollama_host = await self._service_config.get("ollama_host")
            if ollama_host:
                embedding_args["api_base"] = ollama_host
        try:
            response = await litellm.aembedding(**embedding_args)
            vector: list[float] = response.data[0]["embedding"]
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
