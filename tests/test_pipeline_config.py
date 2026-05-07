from __future__ import annotations

from harmony.api.services.pipeline_config import PipelineConfig


def test_pipeline_config_defaults() -> None:
    config = PipelineConfig()
    assert config.keyword_candidates_n == 50  # noqa: PLR2004
    assert config.vector_top_k == 20  # noqa: PLR2004
    assert config.search_top_k == 5  # noqa: PLR2004
    assert config.vector_search_enabled is True
    assert config.reranker_enabled is False


def test_pipeline_config_mutable() -> None:
    config = PipelineConfig()
    config.reranker_enabled = True
    config.keyword_candidates_n = 100
    assert config.reranker_enabled is True
    assert config.keyword_candidates_n == 100  # noqa: PLR2004
