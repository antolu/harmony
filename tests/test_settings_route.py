from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock

import pytest

from harmony.api.routes.settings import (
    PipelineConfigUpdate,
    get_pipeline_config,
    update_pipeline_config,
)
from harmony.api.services.pipeline_config import PipelineConfig


def _make_request(config: PipelineConfig) -> MagicMock:
    request = MagicMock()
    request.app.state.pipeline_config = config
    return request


@pytest.mark.asyncio
async def test_get_pipeline_returns_all_fields() -> None:
    config = PipelineConfig()
    request = _make_request(config)
    result = await get_pipeline_config(request)
    assert result == dataclasses.asdict(config)
    assert "reranker_enabled" in result
    assert "keyword_candidates_n" in result


@pytest.mark.asyncio
async def test_patch_pipeline_updates_reranker_enabled() -> None:
    config = PipelineConfig()
    request = _make_request(config)
    update = PipelineConfigUpdate(reranker_enabled=True)
    await update_pipeline_config(update, request)
    assert config.reranker_enabled is True


@pytest.mark.asyncio
async def test_patch_pipeline_updates_multiple_fields() -> None:
    config = PipelineConfig()
    request = _make_request(config)
    update = PipelineConfigUpdate(keyword_candidates_n=100, search_top_k=10)
    await update_pipeline_config(update, request)
    assert config.keyword_candidates_n == 100  # noqa: PLR2004
    assert config.search_top_k == 10  # noqa: PLR2004


@pytest.mark.asyncio
async def test_patch_pipeline_returns_current_config() -> None:
    config = PipelineConfig()
    request = _make_request(config)
    update = PipelineConfigUpdate(vector_search_enabled=False)
    result = await update_pipeline_config(update, request)
    assert result["vector_search_enabled"] is False
    assert "keyword_candidates_n" in result
    assert "search_top_k" in result


@pytest.mark.asyncio
async def test_patch_pipeline_ignores_none_fields() -> None:
    config = PipelineConfig(keyword_candidates_n=50)
    request = _make_request(config)
    update = PipelineConfigUpdate(reranker_enabled=True)
    await update_pipeline_config(update, request)
    assert config.keyword_candidates_n == 50  # noqa: PLR2004
    assert config.reranker_enabled is True


@pytest.mark.asyncio
async def test_patch_mutates_config_in_place() -> None:
    config = PipelineConfig()
    request = _make_request(config)
    original_id = id(config)
    update = PipelineConfigUpdate(reranker_enabled=True)
    await update_pipeline_config(update, request)
    assert id(request.app.state.pipeline_config) == original_id
