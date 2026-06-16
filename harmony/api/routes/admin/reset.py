from __future__ import annotations

import typing

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from harmony.api.dependencies import (
    get_es_service,
    get_service_config_store,
    require_role,
)
from harmony.api.services import ElasticsearchService
from harmony.api.services.admin import ServiceConfigStore

router = APIRouter()


class ResetRequest(BaseModel):
    confirm: bool = Field(..., description="Must be true to confirm reset operation")


class ResetResponse(BaseModel):
    success: bool
    message: str
    indices_deleted: list[str] = Field(default_factory=list)


@router.post("/crawl-state", response_model=ResetResponse)
async def reset_crawl_state(
    request: ResetRequest,
    es_service: ElasticsearchService = Depends(get_es_service),
    service_config: ServiceConfigStore = Depends(get_service_config_store),
) -> ResetResponse:
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Reset not confirmed. Set confirm=true to proceed.",
        )

    try:
        return await _do_reset_crawl_state(es_service, service_config)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


async def _do_reset_crawl_state(
    es_service: ElasticsearchService,
    service_config: ServiceConfigStore,
) -> ResetResponse:
    if not await es_service.health_check():
        raise HTTPException(status_code=503, detail="Cannot connect to Elasticsearch")

    index_name = await service_config.get("es_state_index")
    deleted_indices = []

    if await es_service.index_exists(index_name):
        await es_service.delete_index(index_name)
        deleted_indices.append(index_name)

    return ResetResponse(
        success=True,
        message=f"Deleted {len(deleted_indices)} index(es)",
        indices_deleted=deleted_indices,
    )


@router.post("/search-indices", response_model=ResetResponse)
async def reset_search_indices(
    request: ResetRequest,
    es_service: ElasticsearchService = Depends(get_es_service),
    service_config: ServiceConfigStore = Depends(get_service_config_store),
) -> ResetResponse:
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Reset not confirmed. Set confirm=true to proceed.",
        )

    try:
        return await _do_reset_search_indices(es_service, service_config)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


async def _do_reset_search_indices(
    es_service: ElasticsearchService,
    service_config: ServiceConfigStore,
) -> ResetResponse:
    if not await es_service.health_check():
        raise HTTPException(status_code=503, detail="Cannot connect to Elasticsearch")

    index_base = await service_config.get("es_index_base_name")
    state_index = await service_config.get("es_state_index")
    pattern = f"{index_base}-*"

    indices = await es_service.list_indices(pattern)
    deleted_indices = []

    for index_name in indices:
        if index_name != state_index:
            await es_service.delete_index(index_name)
            deleted_indices.append(index_name)

    return ResetResponse(
        success=True,
        message=f"Deleted {len(deleted_indices)} index(es)",
        indices_deleted=deleted_indices,
    )


@router.get("/status")
async def get_index_status(
    es_service: ElasticsearchService = Depends(get_es_service),
    service_config: ServiceConfigStore = Depends(get_service_config_store),
) -> dict[str, list[dict[str, str | int]]]:
    try:
        return {"indices": await _do_get_index_status(es_service, service_config)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


async def _do_get_index_status(
    es_service: ElasticsearchService,
    service_config: ServiceConfigStore,
) -> list[dict[str, str | int]]:
    if not await es_service.health_check():
        raise HTTPException(status_code=503, detail="Cannot connect to Elasticsearch")

    indices_info = []
    index_base = await service_config.get("es_index_base_name")
    state_index = await service_config.get("es_state_index")

    if await es_service.index_exists(state_index):
        stats = await es_service.get_index_stats(state_index)
        doc_count = stats["indices"][state_index]["total"]["docs"]["count"]
        indices_info.append({
            "name": state_index,
            "type": "state",
            "doc_count": doc_count,
        })

    pattern = f"{index_base}-*"
    search_indices = await es_service.list_indices(pattern)
    for index_name in search_indices:
        if index_name != state_index:
            stats = await es_service.get_index_stats(index_name)
            doc_count = stats["indices"][index_name]["total"]["docs"]["count"]
            lang = index_name.replace(f"{index_base}-", "")
            indices_info.append({
                "name": index_name,
                "type": "search",
                "language": lang,
                "doc_count": doc_count,
            })
    return indices_info


@router.get("/qdrant-status")
async def get_qdrant_status(
    request: Request,
    _: object = Depends(require_role("read-only")),
) -> dict[str, typing.Any]:
    qdrant_service = getattr(request.app.state, "qdrant_service", None)
    if qdrant_service is None:
        return {"available": False, "reason": "Qdrant not configured"}
    try:
        exists = await qdrant_service.collection_exists()
        if not exists:
            return {
                "available": True,
                "collection": qdrant_service.collection,
                "exists": False,
            }
        vector_size, embedding_model = await qdrant_service.get_collection_info()
        points_count = await qdrant_service.get_points_count()
    except Exception as e:
        return {"available": False, "reason": str(e)}
    else:
        return {
            "available": True,
            "collection": qdrant_service.collection,
            "exists": True,
            "points_count": points_count,
            "vector_size": vector_size,
            "embedding_model": embedding_model,
        }
