from __future__ import annotations

import dataclasses
from unittest.mock import AsyncMock, MagicMock

import pytest

from harmony.api.routes.settings import (
    PipelineConfigUpdate,
    get_pipeline_config_endpoint,
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
    result = await get_pipeline_config_endpoint(pipeline_config=config)
    assert result == dataclasses.asdict(config)
    assert "reranker_enabled" in result
    assert "keyword_candidates_n" in result


@pytest.mark.asyncio
async def test_patch_pipeline_updates_reranker_enabled() -> None:
    config = PipelineConfig()
    request = _make_request(config)
    update = PipelineConfigUpdate(reranker_enabled=True)
    service_config = AsyncMock()
    await update_pipeline_config(update, request, service_config)
    assert request.app.state.pipeline_config.reranker_enabled is True


@pytest.mark.asyncio
async def test_patch_pipeline_updates_multiple_fields() -> None:
    config = PipelineConfig()
    request = _make_request(config)
    update = PipelineConfigUpdate(keyword_candidates_n=100, search_top_k=10)
    service_config = AsyncMock()
    await update_pipeline_config(update, request, service_config)
    new_config = request.app.state.pipeline_config
    assert new_config.keyword_candidates_n == 100
    assert new_config.search_top_k == 10


@pytest.mark.asyncio
async def test_patch_pipeline_returns_current_config() -> None:
    config = PipelineConfig()
    request = _make_request(config)
    update = PipelineConfigUpdate(vector_search_enabled=False)
    service_config = AsyncMock()
    result = await update_pipeline_config(update, request, service_config)
    assert result["vector_search_enabled"] is False
    assert "keyword_candidates_n" in result
    assert "search_top_k" in result


@pytest.mark.asyncio
async def test_patch_pipeline_ignores_none_fields() -> None:
    config = PipelineConfig(keyword_candidates_n=50)
    request = _make_request(config)
    update = PipelineConfigUpdate(reranker_enabled=True)
    service_config = AsyncMock()
    await update_pipeline_config(update, request, service_config)
    new_config = request.app.state.pipeline_config
    assert new_config.keyword_candidates_n == 50
    assert new_config.reranker_enabled is True


@pytest.mark.asyncio
async def test_patch_creates_new_frozen_instance() -> None:
    config = PipelineConfig()
    request = _make_request(config)
    original_id = id(config)
    update = PipelineConfigUpdate(reranker_enabled=True)
    service_config = AsyncMock()
    await update_pipeline_config(update, request, service_config)
    assert id(request.app.state.pipeline_config) != original_id
