from __future__ import annotations

import typing

import structlog

from harmony.tools import (
    FetchDocumentTool,
    FetchPDFTool,
    FetchURLTool,
    GetDocumentDetailsTool,
    SearchDocumentsTool,
    ToolRegistry,
)

if typing.TYPE_CHECKING:
    from harmony.clients import ElasticsearchService
    from harmony.services import DocumentCacheProtocol, SearchService
    from harmony.services.admin import ServiceConfigStore

logger = structlog.get_logger(__name__)


def init_tool_registry(
    es_service: ElasticsearchService,
    search_service: SearchService,
    document_cache: DocumentCacheProtocol,
    service_config: ServiceConfigStore,
) -> ToolRegistry:
    tool_registry = ToolRegistry()
    tool_registry.register(
        SearchDocumentsTool(
            search_service=search_service, service_config=service_config
        )
    )
    tool_registry.register(GetDocumentDetailsTool(es_service=es_service))
    tool_registry.register(
        FetchURLTool(document_cache=document_cache, es_service=es_service)
    )
    tool_registry.register(FetchPDFTool(document_cache=document_cache))
    tool_registry.register(FetchDocumentTool(document_cache=document_cache))
    logger.info(f"Registered {len(tool_registry.tools)} built-in tools")
    return tool_registry
