from __future__ import annotations

import logging
import typing

from fastapi import APIRouter, Query

from harmony.api.config import settings
from harmony.api.services.elasticsearch import es_service
from harmony.api.services.language_detection import language_detector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def search(
    q: str = Query(..., description="Search query"),
    index: str | None = Query(default=None, description="Elasticsearch index name"),
    lang: str | None = Query(default=None, description="Language preference (en, fr)"),
) -> dict[str, typing.Any]:
    """
    Direct Elasticsearch search endpoint with automatic language detection.

    Args:
        q: Search query string
        index: Elasticsearch index (overrides language detection)
        lang: Optional language preference for language-specific search

    Returns:
        Elasticsearch search response with hits and language metadata
    """
    if index:
        response = await es_service.search(query=q, index=index, language=lang)
    else:
        detected_lang, confidence = language_detector.detect_with_confidence(q)

        logger.info(
            f"Query: {q} | Detected: {detected_lang} (confidence: {confidence:.2f})"
        )

        use_detected = (
            detected_lang
            if confidence
            >= settings.es_config.mutable.language_detection_confidence_threshold
            else None
        )

        response = await es_service.search_multilingual(
            query=q,
            detected_language=use_detected or lang,
        )

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
            "snippet": source.get("content", "")[:300],
        }

        if "highlight" in hit:
            formatted_hit["highlights"] = hit["highlight"]

        hits.append(formatted_hit)

    result = {
        "total": response["hits"]["total"]["value"],
        "max_score": response["hits"]["max_score"],
        "hits": hits,
    }

    if "_search_metadata" in response:
        result["search_metadata"] = response["_search_metadata"]

    return result
