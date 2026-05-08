from __future__ import annotations

import dataclasses

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from harmony.api.dependencies import get_pipeline_config, get_service_config_store
from harmony.api.services.admin.service_config import ServiceConfigStore
from harmony.api.services.pipeline_config import PipelineConfig

router = APIRouter(prefix="/settings", tags=["settings"])


class PipelineConfigUpdate(BaseModel):
    keyword_candidates_n: int | None = None
    vector_top_k: int | None = None
    search_top_k: int | None = None
    vector_search_enabled: bool | None = None
    reranker_enabled: bool | None = None


@router.get("/pipeline")
async def get_pipeline_config_endpoint(
    pipeline_config: PipelineConfig = Depends(get_pipeline_config),
) -> dict[str, object]:
    return dataclasses.asdict(pipeline_config)


@router.patch("/pipeline")
async def update_pipeline_config(
    update: PipelineConfigUpdate,
    request: Request,
    service_config: ServiceConfigStore = Depends(get_service_config_store),
) -> dict[str, object]:
    current: PipelineConfig = request.app.state.pipeline_config
    changes = {
        k: v
        for k, v in update.model_dump(exclude_none=True).items()
        if hasattr(current, k)
    }
    for field, value in changes.items():
        await service_config.set(f"pipeline_{field}", str(value))
    new_config = dataclasses.replace(current, **changes)
    request.app.state.pipeline_config = new_config
    return dataclasses.asdict(new_config)
