from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class PipelineConfig:
    keyword_candidates_n: int = 50
    vector_top_k: int = 20
    search_top_k: int = 5
    vector_search_enabled: bool = True
    reranker_enabled: bool = False
    agentic_max_refinement_rounds: int = 3
    agentic_max_query_variants: int = 4
    agentic_search_top_k: int = 10
    agentic_max_sources_returned: int = 10
    search_results_size: int = 10
