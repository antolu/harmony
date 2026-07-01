from __future__ import annotations

import json
import logging
import typing

import pydantic

from harmony.api.services.admin import ConfigProvider
from harmony.authz import AuthorizationContext
from harmony.clients._elasticsearch import ElasticsearchService
from harmony.core import language_detector
from harmony.models import StatusSinkProtocol
from harmony.services import SearchService
from harmony.services._external_search import ExternalSearchContext
from harmony.services._search import SearchContext

logger = logging.getLogger(__name__)

_CHARS_PER_TOKEN = 4
_TRUNCATION_MARKER = (
    "\n\n[…truncated — call get_document_details for the full document]"
)


def _allocate_content_budget(contents: list[str], char_budget: int) -> list[str]:
    """Distribute a shared char budget across score-ordered document contents.

    Contents arrive highest-score first. Each document is granted at least an even
    split of the *remaining* budget, so a single strong hit can claim a large slice
    while later hits still receive their share; a document shorter than its grant
    returns the unused chars to the pool. Nothing is permanently lost — truncated
    documents carry a marker pointing at get_document_details for the full text.
    """
    allocated: list[str] = []
    remaining_budget = char_budget
    for i, content in enumerate(contents):
        docs_left = len(contents) - i
        grant = max(remaining_budget // docs_left, 0)
        if len(content) <= grant:
            allocated.append(content)
            remaining_budget -= len(content)
        else:
            allocated.append(content[:grant].rstrip() + _TRUNCATION_MARKER)
            remaining_budget -= grant
    return allocated


class SearchDocumentsTool:
    """Tool to search documents in the knowledge base."""

    name = "search_documents"
    description = (
        "Search for documents in the knowledge base. "
        "Pass a natural-language query for semantic/vector search, and optionally "
        "short keyword phrases (2-6 words each) for precise keyword matching. "
        "Returns relevant documents with titles, content, URLs, and a document_id. "
        "Each result's content may be truncated to fit a shared budget; when it ends "
        "with an ellipsis, call get_document_details with its document_id to read the "
        "full document instead of fetching its URL over the network."
    )
    parameters: typing.ClassVar[dict[str, pydantic.JsonValue]] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural-language search query used for semantic/vector search",
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Short keyword phrases (2-6 words) for keyword/BM25 search. If omitted, the query is used for keyword search as well.",
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
        service_config: ConfigProvider,
        authz_context: AuthorizationContext | None = None,
        external_context: ExternalSearchContext | None = None,
        sources: list[str] | None = None,
    ) -> None:
        self._search_service = search_service
        self._service_config = service_config
        self._authz_context = authz_context
        self._external_context = external_context
        self._sources = sources

    async def execute(
        self, sink: StatusSinkProtocol, **kwargs: pydantic.JsonValue
    ) -> str:
        try:
            return await self._execute_search(**kwargs)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def _execute_search(self, **kwargs: pydantic.JsonValue) -> str:
        query = str(kwargs.get("query", ""))
        raw_keywords = kwargs.get("keywords")
        keyword_variants: list[str] | None = None
        if isinstance(raw_keywords, list):
            keyword_variants = [str(k) for k in raw_keywords if k]

        lang_arg = kwargs.get("language")
        language = str(lang_arg) if lang_arg is not None else None
        if not language:
            detected_lang, confidence = language_detector.detect_with_confidence(query)
            threshold = float(
                await self._service_config.get(
                    "es_language_detection_confidence_threshold"
                )
            )
            language = detected_lang if confidence >= threshold else None

        search_results_size = int(
            await self._service_config.get("pipeline_search_results_size")
        )
        content_token_budget = int(
            await self._service_config.get("pipeline_search_content_token_budget")
        )
        context = SearchContext(
            query=query,
            primary_query=query,
            keyword_variants=keyword_variants,
            language=language,
            top_k=search_results_size,
            authz_context=self._authz_context,
            external_context=self._external_context,
            sources=self._sources,
        )
        hits = await self._search_service.search(context)

        contents = _allocate_content_budget(
            [str(h.metadata.get("content", "")) for h in hits],
            content_token_budget * _CHARS_PER_TOKEN,
        )
        results = [
            {
                "title": h.metadata.get("title", ""),
                "url": h.path,
                "document_id": h.path,
                "content": content,
                "language": h.metadata.get("language", "unknown"),
                "score": h.score,
                "source_type": h.metadata.get("source_type", "indexed"),
            }
            for h, content in zip(hits, contents, strict=True)
        ]
        return json.dumps({"total": len(results), "results": results}, indent=2)


class GetDocumentDetailsTool:
    """Tool to get full document content by ID."""

    name = "get_document_details"
    description = (
        "Get the full, untruncated content of a document already in the knowledge "
        "base by its document_id (the document_id field from search_documents "
        "results). Prefer this over fetch_url whenever a search result's content was "
        "truncated or you need more of a document found in search — it reads straight "
        "from the index with no network fetch."
    )
    parameters: typing.ClassVar[dict[str, pydantic.JsonValue]] = {
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "The document_id from search_documents results",
            }
        },
        "required": ["document_id"],
    }

    def __init__(self, es_service: ElasticsearchService) -> None:
        self._es_service = es_service

    async def execute(
        self, sink: StatusSinkProtocol, **kwargs: pydantic.JsonValue
    ) -> str:
        document_id = str(kwargs.get("document_id", ""))
        try:
            doc = await self._es_service.get_document(doc_id=document_id)
            return json.dumps(doc, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})
