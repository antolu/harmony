from __future__ import annotations

import logging

import pydantic
from fastapi import APIRouter, Depends, Query

from harmony.api.authz import AuthorizationContext
from harmony.api.config import settings
from harmony.api.dependencies import get_authz_context, get_search_service
from harmony.api.services import SearchService
from harmony.api.services._external_search import ExternalSearchContext
from harmony.core import language_detector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def search(
    q: str = Query(..., description="Search query"),
    lang: str | None = Query(default=None, description="Language preference (en, fr)"),
    use_external_search: bool = Query(  # noqa: FBT001
        default=False, description="Enable external web search providers"
    ),
    search_service: SearchService = Depends(get_search_service),
    authz_context: AuthorizationContext = Depends(get_authz_context),
) -> dict[str, pydantic.JsonValue]:
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

    ext_ctx = ExternalSearchContext(request_toggle=use_external_search)

    hits = await search_service.search(
        q,
        language=language,
        top_k=settings.search_results_size,
        authz_context=authz_context,
        external_context=ext_ctx,
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
                "source_type": h.metadata.get("source_type", "internal"),
                "provider": h.metadata.get("provider", ""),
            }
            for h in hits
        ],
    }
