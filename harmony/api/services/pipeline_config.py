from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class PipelineConfig:
    keyword_candidates_n: int = 50
    vector_top_k: int = 20
    search_top_k: int = 5
    vector_search_enabled: bool = True
    reranker_enabled: bool = False
