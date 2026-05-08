from __future__ import annotations

import dataclasses

import pytest


def test_pipeline_config_is_frozen() -> None:
    from harmony.api.services import PipelineConfig

    cfg = PipelineConfig()
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        cfg.search_top_k = 99  # type: ignore[misc]


def test_pipeline_config_replace() -> None:
    from harmony.api.services import PipelineConfig

    cfg = PipelineConfig()
    new_cfg = dataclasses.replace(cfg, search_top_k=99)
    assert new_cfg.search_top_k == 99
    assert cfg.search_top_k != 99
