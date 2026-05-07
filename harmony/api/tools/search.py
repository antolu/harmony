from __future__ import annotations

import json
import logging
import typing

from harmony.api.config import settings
from harmony.api.services import search as search_module
from harmony.api.services.elasticsearch import es_service
from harmony.core.language_detection import language_detector

if typing.TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SearchDocumentsTool:
    """Tool to search documents in the knowledge base."""

    name = "search_documents"
    description = (
        "Search for documents in the knowledge base using a query. "
        "Returns relevant documents with titles, content snippets, and URLs."
    )
    parameters: typing.ClassVar[dict[str, typing.Any]] = {
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

            assert search_module.search_service is not None
            hits = await search_module.search_service.search(
                query,
                language=language,
                top_k=settings.search_results_size,
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
    parameters: typing.ClassVar[dict[str, typing.Any]] = {
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "The document ID from search results",
            }
        },
        "required": ["document_id"],
    }

    async def execute(self, document_id: str) -> str:
        """
        Get full document content by ID.

        Args:
            document_id: Document ID

        Returns:
            JSON string of document content
        """
        try:
            doc = await es_service.get_document(doc_id=document_id)
            return json.dumps(doc, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})


# Tool instances
search_documents_tool = SearchDocumentsTool()
get_document_details_tool = GetDocumentDetailsTool()


# Legacy compatibility - deprecated
SEARCH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": search_documents_tool.description,
            "parameters": search_documents_tool.parameters,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_document_details",
            "description": get_document_details_tool.description,
            "parameters": get_document_details_tool.parameters,
        },
    },
]


async def execute_tool(tool_name: str, arguments: dict[str, typing.Any]) -> str:
    """
    Legacy compatibility function.
    Execute a tool function and return the result as a string.

    Args:
        tool_name: Name of the tool to execute
        arguments: Tool arguments

    Returns:
        Tool execution result as JSON string
    """
    if tool_name == "search_documents":
        return await search_documents_tool.execute(**arguments)
    if tool_name == "get_document_details":
        return await get_document_details_tool.execute(**arguments)
    return json.dumps({"error": f"Unknown tool: {tool_name}"})
