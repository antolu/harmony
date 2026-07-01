from __future__ import annotations

from harmony.services import PipelineConfig
from harmony.services.admin import ConfigProvider


async def load_pipeline_config(service_config: ConfigProvider) -> PipelineConfig:
    def _int(val: str | None, default: int) -> int:
        try:
            return int(val) if val else default
        except ValueError:
            return default

    def _bool(val: str | None, *, default: bool) -> bool:
        if not val:
            return default
        return val.lower() in {"true", "1", "yes"}

    return PipelineConfig(
        keyword_candidates_n=_int(
            await service_config.get("pipeline_keyword_candidates_n"), 50
        ),
        vector_top_k=_int(await service_config.get("pipeline_vector_top_k"), 20),
        search_top_k=_int(await service_config.get("pipeline_search_top_k"), 5),
        vector_search_enabled=_bool(
            await service_config.get("pipeline_vector_search_enabled"), default=True
        ),
        reranker_enabled=_bool(
            await service_config.get("pipeline_reranker_enabled"), default=False
        ),
        agentic_max_refinement_rounds=_int(
            await service_config.get("pipeline_agentic_max_refinement_rounds"), 3
        ),
        agentic_max_query_variants=_int(
            await service_config.get("pipeline_agentic_max_query_variants"), 4
        ),
        agentic_search_top_k=_int(
            await service_config.get("pipeline_agentic_search_top_k"), 10
        ),
        agentic_max_sources_returned=_int(
            await service_config.get("pipeline_agentic_max_sources_returned"), 10
        ),
        search_results_size=_int(
            await service_config.get("pipeline_search_results_size"), 10
        ),
        embedding_batch_size=_int(
            await service_config.get("pipeline_embedding_batch_size"), 64
        ),
        ai_search_max_iterations=_int(
            await service_config.get("pipeline_ai_search_max_iterations"), 3
        ),
        ai_search_source_token_budget=_int(
            await service_config.get("pipeline_ai_search_source_token_budget"), 12_000
        ),
    )
