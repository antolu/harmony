from __future__ import annotations

import dataclasses
import logging
import typing

import litellm
import structlog.contextvars
from kv_search import RerankerBackend, SearchHit

from harmony.api.services.admin import ModelSettingsStore
from harmony.api.services.admin._service_config import ServiceConfigStore

logger = logging.getLogger(__name__)


class HarmonyRerankerBackend(RerankerBackend):
    _LOCAL_PREFIXES: typing.ClassVar[tuple[str, ...]] = ("ollama/", "ollama_chat/")

    def __init__(
        self,
        *,
        service_config: ServiceConfigStore,
        model_settings_store: ModelSettingsStore,
    ) -> None:
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

    async def rerank(
        self,
        query: str,
        candidates: list[SearchHit],
        *,
        top_n: int,
    ) -> list[SearchHit]:
        reranker_model = await self._model_settings_store.get_reranker_model()
        await self._assert_data_residency(reranker_model)
        docs = [h.metadata.get("content", h.path) for h in candidates]
        try:
            response = await litellm.arerank(
                model=reranker_model,
                query=query,
                documents=docs,
                top_n=top_n,
                metadata={
                    "trace_id": structlog.contextvars.get_contextvars().get(
                        "trace_id", ""
                    ),
                    "agent_step": "reranker",
                },
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
