from __future__ import annotations

import logging
import typing

from fastapi import APIRouter, Query

from harmony.api.config import settings
from harmony.api.services import search as search_module
from harmony.api.services.language_detection import language_detector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def search(
    q: str = Query(..., description="Search query"),
    lang: str | None = Query(default=None, description="Language preference (en, fr)"),
) -> dict[str, typing.Any]:
    detected_lang, confidence = language_detector.detect_with_confidence(q)
    logger.info(
        "Query: %s | Detected: %s (confidence: %.2f)", q, detected_lang, confidence
    )

    language = lang or (
        detected_lang
        if confidence
        >= settings.es_config.mutable.language_detection_confidence_threshold
        else None
    )

    assert search_module.search_service is not None
    hits = await search_module.search_service.search(
        q,
        language=language,
        top_k=settings.search_results_size,
    )

    return {
        "total": len(hits),
        "max_score": hits[0].score if hits else None,
        "hits": [
            {
                "score": h.score,
                "title": h.metadata.get("title", ""),
                "url": h.path,
                "language": h.metadata.get("language", ""),
                "domain": h.metadata.get("domain", ""),
                "snippet": str(h.metadata.get("content", ""))[:300],
            }
            for h in hits
        ],
    }
