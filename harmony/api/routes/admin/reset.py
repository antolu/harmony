from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from harmony.api.config import settings

router = APIRouter()


class ResetRequest(BaseModel):
    confirm: bool = Field(..., description="Must be true to confirm reset operation")


class ResetResponse(BaseModel):
    success: bool
    message: str
    indices_deleted: list[str] = Field(default_factory=list)


@router.post("/crawl-state", response_model=ResetResponse)
async def reset_crawl_state(request: ResetRequest) -> ResetResponse:
    """Delete the crawl state index. Requires confirm=true."""
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Reset not confirmed. Set confirm=true to proceed.",
        )

    try:
        from elasticsearch import Elasticsearch  # noqa: PLC0415

        es = Elasticsearch([settings.es_host])

        if not es.ping():
            raise HTTPException(  # noqa: TRY301
                status_code=503, detail="Cannot connect to Elasticsearch"
            )

        index_name = settings.es_state_index
        deleted_indices = []

        if es.indices.exists(index=index_name):
            es.indices.delete(index=index_name)
            deleted_indices.append(index_name)

        return ResetResponse(
            success=True,
            message=f"Deleted {len(deleted_indices)} index(es)",
            indices_deleted=deleted_indices,
        )

    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail="Elasticsearch client not installed. Install with: pip install elasticsearch",
        ) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/search-indices", response_model=ResetResponse)
async def reset_search_indices(request: ResetRequest) -> ResetResponse:
    """Delete all search indices. Requires confirm=true."""
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Reset not confirmed. Set confirm=true to proceed.",
        )

    try:
        from elasticsearch import Elasticsearch  # noqa: PLC0415

        es = Elasticsearch([settings.es_host])

        if not es.ping():
            raise HTTPException(  # noqa: TRY301
                status_code=503, detail="Cannot connect to Elasticsearch"
            )

        pattern = f"{settings.es_index_base_name}-*"
        indices = list(es.indices.get(index=pattern).keys())
        deleted_indices = []

        for index_name in indices:
            if index_name != settings.es_state_index:
                es.indices.delete(index=index_name)
                deleted_indices.append(index_name)

        return ResetResponse(
            success=True,
            message=f"Deleted {len(deleted_indices)} index(es)",
            indices_deleted=deleted_indices,
        )

    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail="Elasticsearch client not installed. Install with: pip install elasticsearch",
        ) from e
    except Exception as e:
        if "index_not_found_exception" in str(e):
            return ResetResponse(
                success=True,
                message="No indices found to delete",
                indices_deleted=[],
            )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/status")
async def get_index_status() -> dict[str, list[dict[str, str | int]]]:
    """Get status of all indices."""
    try:
        from elasticsearch import Elasticsearch  # noqa: PLC0415

        es = Elasticsearch([settings.es_host])

        if not es.ping():
            raise HTTPException(  # noqa: TRY301
                status_code=503, detail="Cannot connect to Elasticsearch"
            )

        indices_info = []

        state_index = settings.es_state_index
        if es.indices.exists(index=state_index):
            stats = es.indices.stats(index=state_index)
            doc_count = stats["indices"][state_index]["total"]["docs"]["count"]
            indices_info.append({
                "name": state_index,
                "type": "state",
                "doc_count": doc_count,
            })

        pattern = f"{settings.es_index_base_name}-*"
        try:
            search_indices = es.indices.get(index=pattern)
            for index_name in search_indices:
                if index_name != state_index:
                    stats = es.indices.stats(index=index_name)
                    doc_count = stats["indices"][index_name]["total"]["docs"]["count"]
                    lang = index_name.replace(f"{settings.es_index_base_name}-", "")
                    indices_info.append({
                        "name": index_name,
                        "type": "search",
                        "language": lang,
                        "doc_count": doc_count,
                    })
        except Exception:
            pass

    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail="Elasticsearch client not installed",
        ) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        return {"indices": indices_info}
