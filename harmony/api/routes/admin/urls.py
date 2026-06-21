from __future__ import annotations

import dataclasses
import typing

import pydantic
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from harmony.api.dependencies import require_role
from harmony.api.models.user import AnonymousIdentity, UserIdentity
from harmony.core import url_to_id

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin/documents", tags=["admin"])

_STATE_INDEX = "harmony-crawl-state"
_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200


class AddBlacklistBody(BaseModel):
    pattern: str
    reason: str | None = None


class ListUrlsParams(BaseModel):
    domain: str | None = None
    language: str | None = None
    query: str | None = None
    limit: int = _DEFAULT_LIMIT
    offset: int = 0


@router.get("")
async def list_urls(
    request: Request,
    params: typing.Annotated[ListUrlsParams, Depends()],
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> dict[str, pydantic.JsonValue]:
    limit = min(params.limit, _MAX_LIMIT)
    es = request.app.state.es_service.client

    must: list[pydantic.JsonValue] = []
    if params.domain:
        domain = params.domain
        pattern = domain if "*" in domain or "?" in domain else f"*{domain}*"
        must.append({
            "wildcard": {"domain": {"value": pattern, "case_insensitive": True}}
        })
    if params.language:
        must.append({"term": {"language": params.language}})
    if params.query:
        query = params.query
        url_pattern = query if "*" in query or "?" in query else f"*{query}*"
        must.append({
            "wildcard": {"url": {"value": url_pattern, "case_insensitive": True}}
        })

    es_query: dict[str, pydantic.JsonValue] = (
        {"match_all": {}} if not must else {"bool": {"must": must}}
    )

    response = await es.search(
        index=_STATE_INDEX,
        query=es_query,
        from_=params.offset,
        size=limit,
        source_includes=[
            "url",
            "domain",
            "language",
            "title",
            "crawled_at",
            "last_crawled_at",
            "status",
        ],
        ignore_unavailable=True,
    )
    hits = response.get("hits", {})
    total = hits.get("total", {}).get("value", 0)
    urls = [
        {
            "id": hit["_id"],
            **hit.get("_source", {}),
        }
        for hit in hits.get("hits", [])
    ]
    return {"urls": urls, "total": total}


@router.delete("/{url_id:path}")
async def delete_document_atomic(
    url_id: str,
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> dict[str, str]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    es = request.app.state.es_service.client
    qdrant_service = request.app.state.qdrant_service
    audit_log = request.app.state.audit_log_service

    try:
        doc_response = await es.get(index=_STATE_INDEX, id=url_id, ignore=[404])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ES read failed: {exc}") from exc

    if not doc_response.get("found"):
        raise HTTPException(status_code=404, detail=f"Document '{url_id}' not found")

    saved_source = doc_response.get("_source", {})

    try:
        await es.delete(index=_STATE_INDEX, id=url_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ES delete failed: {exc}") from exc

    if qdrant_service is not None:
        qdrant_point_id = url_to_id(url_id)
        try:
            await qdrant_service.delete_points([qdrant_point_id])
        except Exception as qdrant_exc:
            try:
                await es.index(
                    index=_STATE_INDEX,
                    id=url_id,
                    document=saved_source,
                )
            except Exception as rollback_exc:
                await audit_log.record(
                    user_id=user_id,
                    action="document_deletion_critical_error",
                    entity_type="crawl_state",
                    entity_id=url_id,
                    details={
                        "state": "INCONSISTENT",
                        "qdrant_error": str(qdrant_exc),
                        "error": str(rollback_exc),
                    },
                )
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": "CRITICAL",
                        "message": f"Qdrant delete failed and ES rollback failed — index is INCONSISTENT: {rollback_exc}",
                    },
                ) from rollback_exc
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "ROLLBACK_EXECUTED",
                    "message": f"Qdrant delete failed, ES document restored. Qdrant error: {qdrant_exc}",
                },
            ) from qdrant_exc

    await audit_log.record(
        user_id=user_id,
        action="document_deleted",
        entity_type="crawl_state",
        entity_id=url_id,
        details={},
    )
    return {"status": "deleted"}


@router.get("/blacklist")
async def list_blacklist_patterns(
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> dict[str, pydantic.JsonValue]:
    patterns = await request.app.state.crawl_blacklist_repo.list()
    return {"patterns": [dataclasses.asdict(p) for p in patterns]}


@router.post("/blacklist")
async def add_blacklist_pattern(
    body: AddBlacklistBody,
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> dict[str, pydantic.JsonValue]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    result = await request.app.state.crawl_blacklist_repo.add(
        pattern=body.pattern,
        reason=body.reason,
        created_by=user_id,
    )
    await request.app.state.audit_log_service.record(
        user_id=user_id,
        action="blacklist_pattern_added",
        entity_type="crawl_blacklist",
        entity_id=str(result.id),
        details={"pattern": body.pattern},
    )
    return dataclasses.asdict(result)


@router.delete("/blacklist/{pattern_id}")
async def remove_blacklist_pattern(
    pattern_id: str,
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> dict[str, bool]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    removed = await request.app.state.crawl_blacklist_repo.remove(pattern_id)
    if not removed:
        raise HTTPException(
            status_code=404, detail=f"Blacklist pattern '{pattern_id}' not found"
        )
    await request.app.state.audit_log_service.record(
        user_id=user_id,
        action="blacklist_pattern_removed",
        entity_type="crawl_blacklist",
        entity_id=pattern_id,
        details={},
    )
    return {"deleted": True}


@router.get("/domains")
async def get_domain_stats(
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> dict[str, pydantic.JsonValue]:
    es = request.app.state.es_service.client

    response = await es.search(
        index=_STATE_INDEX,
        size=0,
        aggregations={
            "domains": {
                "terms": {"field": "domain", "size": 500},
                "aggs": {
                    "languages": {"terms": {"field": "language", "size": 20}},
                    "last_crawled": {"max": {"field": "last_crawled_at"}},
                },
            }
        },
        ignore_unavailable=True,
    )

    buckets = response.get("aggregations", {}).get("domains", {}).get("buckets", [])
    stats: list[pydantic.JsonValue] = [
        {
            "domain": bucket["key"],
            "count": bucket["doc_count"],
            "languages": [
                lang["key"] for lang in bucket.get("languages", {}).get("buckets", [])
            ],
            "last_crawled_at": bucket.get("last_crawled", {}).get("value_as_string"),
        }
        for bucket in buckets
    ]
    return {"domains": stats}
