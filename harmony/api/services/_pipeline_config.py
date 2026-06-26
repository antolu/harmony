from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class PipelineConfig:
    # keyword_candidates_n (ES allowlist width) and vector_top_k (how many of that
    # allowlist get vector-scored) are widened so a spread-out answer's pieces all
    # survive as candidates for the agentic SourcePool char budget to admit. They are
    # coupled to local reranker latency: a larger vector_top_k means more docs for the
    # reranker to score (O(N) cost). Runtime-tunable via PATCH /settings/pipeline.
    keyword_candidates_n: int = 150
    vector_top_k: int = 50
    search_top_k: int = 5
    vector_search_enabled: bool = True
    reranker_enabled: bool = False
    agentic_max_refinement_rounds: int = 3
    agentic_max_query_variants: int = 4
    agentic_search_top_k: int = 10
    agentic_max_sources_returned: int = 10
    search_results_size: int = 10
    embedding_batch_size: int = 64
