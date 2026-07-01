from __future__ import annotations

import dataclasses

import pytest

from harmony.services import PipelineConfig


def test_pipeline_config_defaults() -> None:
    config = PipelineConfig()
    assert config.keyword_candidates_n == 150
    assert config.vector_top_k == 50
    assert config.search_top_k == 5
    assert config.vector_search_enabled is True
    assert config.reranker_enabled is False


def test_pipeline_config_is_frozen() -> None:
    cfg = PipelineConfig()
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        cfg.search_top_k = 99  # type: ignore[misc]


def test_pipeline_config_replace() -> None:
    cfg = PipelineConfig()
    new_cfg = dataclasses.replace(cfg, search_top_k=99)
    assert new_cfg.search_top_k == 99
    assert cfg.search_top_k != 99


def test_pipeline_config_immutable_replace() -> None:
    config = PipelineConfig()
    new_config = dataclasses.replace(
        config, reranker_enabled=True, keyword_candidates_n=100
    )
    assert new_config.reranker_enabled is True
    assert new_config.keyword_candidates_n == 100
    assert config.reranker_enabled is False
