from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from harmony.api.config import settings
from harmony.api.services.elasticsearch import es_service

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def search(
    q: str = Query(..., description="Search query"),
    index: str = Query(default=None, description="Elasticsearch index name"),
    lang: str | None = Query(default=None, description="Language preference (en, fr)"),
) -> dict[str, Any]:
    """
    Direct Elasticsearch search endpoint for debugging.

    Args:
        q: Search query string
        index: Elasticsearch index (default from settings)
        lang: Optional language preference for field boosting

    Returns:
        Elasticsearch search response with hits
    """
    index = index or settings.es_index
    response = await es_service.search(query=q, index=index, language=lang)

    # Format response for easier consumption
    hits = []
    for hit in response["hits"]["hits"]:
        source = hit["_source"]
        formatted_hit = {
            "id": hit["_id"],
            "score": hit["_score"],
            "title": source.get("title", ""),
            "url": source.get("url", ""),
            "language": source.get("language", ""),
            "domain": source.get("domain", ""),
            "snippet": source.get("content", "")[:300],  # First 300 chars
        }

        # Add highlights if available
        if "highlight" in hit:
            formatted_hit["highlights"] = hit["highlight"]

        hits.append(formatted_hit)

    return {
        "total": response["hits"]["total"]["value"],
        "max_score": response["hits"]["max_score"],
        "hits": hits,
    }
