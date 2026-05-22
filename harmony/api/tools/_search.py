from __future__ import annotations

import json
import logging
import typing

from harmony.api.authz import AuthorizationContext
from harmony.api.config import settings
from harmony.api.services import ElasticsearchService, SearchService
from harmony.core import language_detector

logger = logging.getLogger(__name__)


class SearchDocumentsTool:
    """Tool to search documents in the knowledge base."""

    name = "search_documents"
    description = (
        "Search for documents in the knowledge base using a query. "
        "Returns relevant documents with titles, content snippets, and URLs."
    )
    parameters: dict[str, typing.Any] = {  # noqa: RUF012
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to find relevant documents",
            },
            "language": {
                "type": "string",
                "enum": ["en", "fr"],
                "description": "Optional: Language preference for boosting results (en=English, fr=French)",
            },
        },
        "required": ["query"],
    }

    def __init__(
        self,
        search_service: SearchService,
        authz_context: AuthorizationContext | None = None,
    ) -> None:
        self._search_service = search_service
        self._authz_context = authz_context

    async def execute(self, query: str, language: str | None = None) -> str:
        try:
            if not language:
                detected_lang, confidence = language_detector.detect_with_confidence(
                    query
                )
                language = (
                    detected_lang
                    if confidence
                    >= settings.es_config.mutable.language_detection_confidence_threshold
                    else None
                )

            hits = await self._search_service.search(
                query,
                language=language,
                top_k=settings.search_results_size,
                authz_context=self._authz_context,
            )

            results = [
                {
                    "title": h.metadata.get("title", ""),
                    "url": h.path,
                    "snippet": str(h.metadata.get("content", ""))[:500],
                    "language": h.metadata.get("language", "unknown"),
                    "score": h.score,
                }
                for h in hits
            ]
            return json.dumps({"total": len(results), "results": results}, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})


class GetDocumentDetailsTool:
    """Tool to get full document content by ID."""

    name = "get_document_details"
    description = (
        "Get the full content of a specific document by its ID. "
        "Use this when you need more details about a document found in search results."
    )
    parameters: dict[str, typing.Any] = {  # noqa: RUF012
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "The document ID from search results",
            }
        },
        "required": ["document_id"],
    }

    def __init__(self, es_service: ElasticsearchService) -> None:
        self._es_service = es_service

    async def execute(self, document_id: str) -> str:
        try:
            doc = await self._es_service.get_document(doc_id=document_id)
            return json.dumps(doc, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})
