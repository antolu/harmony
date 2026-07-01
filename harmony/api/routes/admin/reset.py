from __future__ import annotations

import pydantic
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from harmony.api.dependencies import (
    get_es_service,
    get_service_config_store,
    require_role,
)
from harmony.clients._elasticsearch import ElasticsearchService
from harmony.models import AnonymousIdentity, UserIdentity
from harmony.services.admin import ConfigProvider

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
    service_config: ConfigProvider = Depends(get_service_config_store),
    _: None = Depends(require_role("admin")),
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
    service_config: ConfigProvider,
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
    service_config: ConfigProvider = Depends(get_service_config_store),
    _: None = Depends(require_role("admin")),
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
    service_config: ConfigProvider,
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
    service_config: ConfigProvider = Depends(get_service_config_store),
    _: None = Depends(require_role("admin")),
) -> dict[str, list[dict[str, str | int]]]:
    try:
        return {"indices": await _do_get_index_status(es_service, service_config)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


async def _do_get_index_status(
    es_service: ElasticsearchService,
    service_config: ConfigProvider,
) -> list[dict[str, str | int]]:
    if not await es_service.health_check():
        raise HTTPException(status_code=503, detail="Cannot connect to Elasticsearch")

    indices_info: list[dict[str, str | int]] = []
    index_base = await service_config.get("es_index_base_name")
    state_index = await service_config.get("es_state_index")

    if await es_service.index_exists(state_index):
        stats = await es_service.get_index_stats(state_index)
        doc_count = 0
        if (
            isinstance(stats, dict)
            and "indices" in stats
            and isinstance(stats["indices"], dict)
        ):
            idx_st = stats["indices"].get(state_index, {})
            if (
                isinstance(idx_st, dict)
                and "total" in idx_st
                and isinstance(idx_st["total"], dict)
            ):
                docs = idx_st["total"].get("docs", {})
                if isinstance(docs, dict):
                    doc_count = int(str(docs.get("count", 0)))
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
            doc_count = 0
            if (
                isinstance(stats, dict)
                and "indices" in stats
                and isinstance(stats["indices"], dict)
            ):
                idx_st = stats["indices"].get(index_name, {})
                if (
                    isinstance(idx_st, dict)
                    and "total" in idx_st
                    and isinstance(idx_st["total"], dict)
                ):
                    docs = idx_st["total"].get("docs", {})
                    if isinstance(docs, dict):
                        doc_count = int(str(docs.get("count", 0)))
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
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> dict[str, pydantic.JsonValue]:
    qdrant_service = request.app.state.qdrant_service
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
