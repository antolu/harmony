from __future__ import annotations

import asyncio
import logging
import time
import typing

import pydantic
from fastapi import APIRouter, Depends, Request

from harmony.api.config import Settings
from harmony.api.dependencies import (
    get_authz_context,
    get_current_user_or_anonymous,
    get_search_service,
    get_service_config_store,
    get_settings,
)
from harmony.api.services import SearchService
from harmony.api.services._external_search import ExternalSearchContext
from harmony.api.services._search import SearchContext
from harmony.api.services.admin import ConfigProvider
from harmony.authz import AuthorizationContext
from harmony.core import language_detector
from harmony.db.repositories import SearchLogData
from harmony.models import AnonymousIdentity, UserIdentity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

_background_tasks: set[asyncio.Task[None]] = set()


class SearchParams(pydantic.BaseModel):
    q: str = pydantic.Field(..., description="Search query")
    lang: str | None = pydantic.Field(
        default=None, description="Language preference (en, fr)"
    )
    use_external_search: bool = pydantic.Field(
        default=False, description="Enable external web search providers"
    )


@router.get("")
async def search(  # noqa: PLR0913
    request: Request,
    params: typing.Annotated[SearchParams, Depends()],
    search_service: SearchService = Depends(get_search_service),
    authz_context: AuthorizationContext = Depends(get_authz_context),
    current_user: UserIdentity | AnonymousIdentity = Depends(
        get_current_user_or_anonymous
    ),
    service_config: ConfigProvider = Depends(get_service_config_store),
    settings: Settings = Depends(get_settings),
) -> dict[str, pydantic.JsonValue]:
    detected_lang, confidence = language_detector.detect_with_confidence(params.q)
    logger.info(
        "Query: %s | Detected: %s (confidence: %.2f)",
        params.q,
        detected_lang,
        confidence,
    )

    threshold = float(
        await service_config.get("es_language_detection_confidence_threshold")
    )
    language = params.lang or (detected_lang if confidence >= threshold else None)

    ext_ctx = ExternalSearchContext(request_toggle=params.use_external_search)

    start = time.monotonic()
    hits = await search_service.search(
        SearchContext(
            query=params.q,
            language=language,
            top_k=settings.search_results_size,
            authz_context=authz_context,
            external_context=ext_ctx,
        )
    )
    latency_ms = int((time.monotonic() - start) * 1000)

    audit_log_service = getattr(request.app.state, "audit_log_service", None)
    if audit_log_service is not None:
        user_id = (
            current_user.id if isinstance(current_user, UserIdentity) else "anonymous"
        )
        task = asyncio.create_task(
            audit_log_service.record_search(
                SearchLogData(
                    user_id=user_id,
                    query=params.q,
                    language=language,
                    result_count=len(hits),
                    latency_ms=latency_ms,
                    tokens=None,
                    mode="direct",
                )
            )
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

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
