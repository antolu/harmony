from __future__ import annotations

import dataclasses

from fastapi import APIRouter, Request
from pydantic import BaseModel

from harmony.api.services.pipeline_config import PipelineConfig

router = APIRouter(prefix="/settings", tags=["settings"])


class PipelineConfigUpdate(BaseModel):
    keyword_candidates_n: int | None = None
    vector_top_k: int | None = None
    search_top_k: int | None = None
    vector_search_enabled: bool | None = None
    reranker_enabled: bool | None = None
    reranker_model: str | None = None


@router.get("/pipeline")
async def get_pipeline_config(request: Request) -> dict[str, object]:
    config: PipelineConfig = request.app.state.pipeline_config
    return dataclasses.asdict(config)


@router.patch("/pipeline")
async def update_pipeline_config(
    update: PipelineConfigUpdate, request: Request
) -> dict[str, object]:
    config: PipelineConfig = request.app.state.pipeline_config
    for field, value in update.model_dump(exclude_none=True).items():
        if hasattr(config, field):
            setattr(config, field, value)
    return dataclasses.asdict(config)
