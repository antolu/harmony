from __future__ import annotations

from harmony.api.services.pipeline_config import PipelineConfig


def test_pipeline_config_defaults() -> None:
    config = PipelineConfig()
    assert config.keyword_candidates_n == 50
    assert config.vector_top_k == 20
    assert config.search_top_k == 5
    assert config.vector_search_enabled is True
    assert config.reranker_enabled is False


def test_pipeline_config_immutable_replace() -> None:
    import dataclasses

    config = PipelineConfig()
    new_config = dataclasses.replace(
        config, reranker_enabled=True, keyword_candidates_n=100
    )
    assert new_config.reranker_enabled is True
    assert new_config.keyword_candidates_n == 100
    assert config.reranker_enabled is False
