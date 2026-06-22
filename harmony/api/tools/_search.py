from __future__ import annotations

import json
import logging
import typing

import pydantic

from harmony.api.authz import AuthorizationContext
from harmony.api.services import SearchService
from harmony.api.services._search import SearchContext
from harmony.api.services.admin import ServiceConfigStore
from harmony.clients._elasticsearch import ElasticsearchService
from harmony.core import language_detector

if typing.TYPE_CHECKING:
    from harmony.api.services._external_search import ExternalSearchContext

logger = logging.getLogger(__name__)


class SearchDocumentsTool:
    """Tool to search documents in the knowledge base."""

    name = "search_documents"
    description = (
        "Search for documents in the knowledge base using a query. "
        "Returns relevant documents with titles, content snippets, and URLs."
    )
    parameters: typing.ClassVar[dict[str, pydantic.JsonValue]] = {
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
        service_config: ServiceConfigStore,
        authz_context: AuthorizationContext | None = None,
        external_context: ExternalSearchContext | None = None,
        sources: list[str] | None = None,
    ) -> None:
        self._search_service = search_service
        self._service_config = service_config
        self._authz_context = authz_context
        self._external_context = external_context
        self._sources = sources

    async def execute(self, **kwargs: pydantic.JsonValue) -> str:
        query = str(kwargs.get("query", ""))
        lang_arg = kwargs.get("language")
        language = str(lang_arg) if lang_arg is not None else None
        try:  # noqa: PLW0717
            if not language:
                detected_lang, confidence = language_detector.detect_with_confidence(
                    query
                )
                threshold = float(
                    await self._service_config.get(
                        "es_language_detection_confidence_threshold"
                    )
                )
                language = detected_lang if confidence >= threshold else None

            search_results_size = int(
                await self._service_config.get("pipeline_search_results_size")
            )
            hits = await self._search_service.search(
                SearchContext(
                    query=query,
                    language=language,
                    top_k=search_results_size,
                    authz_context=self._authz_context,
                    external_context=self._external_context,
                    sources=self._sources,
                )
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
    parameters: typing.ClassVar[dict[str, pydantic.JsonValue]] = {
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

    async def execute(self, **kwargs: pydantic.JsonValue) -> str:
        document_id = str(kwargs.get("document_id", ""))
        try:
            doc = await self._es_service.get_document(doc_id=document_id)
            return json.dumps(doc, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})
