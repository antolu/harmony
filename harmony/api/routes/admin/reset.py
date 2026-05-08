from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from harmony.api.dependencies import get_es_service, get_service_config_store
from harmony.api.services.admin.service_config import ServiceConfigStore
from harmony.api.services.elasticsearch import ElasticsearchService

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
    """Delete the crawl state index. Requires confirm=true."""
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Reset not confirmed. Set confirm=true to proceed.",
        )

    try:
        if not await es_service.health_check():
            raise HTTPException(  # noqa: TRY301
                status_code=503, detail="Cannot connect to Elasticsearch"
            )

        client = es_service.client
        index_name = await service_config.get("es_state_index") or "harmony-crawl-state"
        deleted_indices = []

        if await client.indices.exists(index=index_name):
            await client.indices.delete(index=index_name)
            deleted_indices.append(index_name)

        return ResetResponse(
            success=True,
            message=f"Deleted {len(deleted_indices)} index(es)",
            indices_deleted=deleted_indices,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/search-indices", response_model=ResetResponse)
async def reset_search_indices(
    request: ResetRequest,
    es_service: ElasticsearchService = Depends(get_es_service),
    service_config: ServiceConfigStore = Depends(get_service_config_store),
) -> ResetResponse:
    """Delete all search indices. Requires confirm=true."""
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Reset not confirmed. Set confirm=true to proceed.",
        )

    try:
        if not await es_service.health_check():
            raise HTTPException(  # noqa: TRY301
                status_code=503, detail="Cannot connect to Elasticsearch"
            )

        client = es_service.client
        index_base = await service_config.get("es_index_base_name") or "harmony"
        state_index = (
            await service_config.get("es_state_index") or "harmony-crawl-state"
        )
        pattern = f"{index_base}-*"

        indices_dict = await client.indices.get(index=pattern)
        indices = list(indices_dict.keys())
        deleted_indices = []

        for index_name in indices:
            if index_name != state_index:
                await client.indices.delete(index=index_name)
                deleted_indices.append(index_name)

        return ResetResponse(
            success=True,
            message=f"Deleted {len(deleted_indices)} index(es)",
            indices_deleted=deleted_indices,
        )

    except HTTPException:
        raise
    except Exception as e:
        if "index_not_found_exception" in str(e):
            return ResetResponse(
                success=True,
                message="No indices found to delete",
                indices_deleted=[],
            )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/status")
async def get_index_status(
    es_service: ElasticsearchService = Depends(get_es_service),
    service_config: ServiceConfigStore = Depends(get_service_config_store),
) -> dict[str, list[dict[str, str | int]]]:
    """Get status of all indices."""
    try:
        if not await es_service.health_check():
            raise HTTPException(  # noqa: TRY301
                status_code=503, detail="Cannot connect to Elasticsearch"
            )

        client = es_service.client
        indices_info = []

        index_base = await service_config.get("es_index_base_name") or "harmony"
        state_index = (
            await service_config.get("es_state_index") or "harmony-crawl-state"
        )

        if await client.indices.exists(index=state_index):
            stats = await client.indices.stats(index=state_index)
            doc_count = stats["indices"][state_index]["total"]["docs"]["count"]
            indices_info.append({
                "name": state_index,
                "type": "state",
                "doc_count": doc_count,
            })

        pattern = f"{index_base}-*"
        try:
            search_indices = await client.indices.get(index=pattern)
            for index_name in search_indices:
                if index_name != state_index:
                    stats = await client.indices.stats(index=index_name)
                    doc_count = stats["indices"][index_name]["total"]["docs"]["count"]
                    lang = index_name.replace(f"{index_base}-", "")
                    indices_info.append({
                        "name": index_name,
                        "type": "search",
                        "language": lang,
                        "doc_count": doc_count,
                    })
        except Exception:
            pass

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        return {"indices": indices_info}
