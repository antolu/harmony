from __future__ import annotations

import logging
import typing
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from harmony.api.backends.keyword import HarmonyKeywordBackend
from harmony.api.backends.reranker import HarmonyRerankerBackend
from harmony.api.backends.vector import HarmonyVectorBackend
from harmony.api.config import settings
from harmony.api.routes import agentic_search, chat, search
from harmony.api.routes import settings as settings_route
from harmony.api.services import search as search_module
from harmony.api.services.document_cache import document_cache
from harmony.api.services.elasticsearch import es_service
from harmony.api.services.pipeline_config import PipelineConfig
from harmony.api.services.prompts import initialize_prompt_manager
from harmony.api.services.qdrant import QdrantService
from harmony.api.services.search import SearchService
from harmony.api.tools.documents import (
    fetch_document_tool,
    fetch_pdf_tool,
    fetch_url_tool,
)
from harmony.api.tools.mcp import MCPServerLoader
from harmony.api.tools.registry import tool_registry
from harmony.api.tools.search import get_document_details_tool, search_documents_tool

logger = logging.getLogger(__name__)


def _build_search_service(
    qdrant_service: QdrantService, pipeline_config: PipelineConfig
) -> tuple[SearchService, HarmonyKeywordBackend]:
    keyword_backend = HarmonyKeywordBackend(
        host=settings.es_config.host,
        index_base_name=settings.es_config.index_base_name,
        languages=settings.es_config.languages,
        boost_title=settings.es_config.mutable.boost_title,
        boost_content=settings.es_config.mutable.boost_content,
        size=pipeline_config.keyword_candidates_n,
    )
    vector_backend = HarmonyVectorBackend(
        qdrant_service=qdrant_service,
        embedding_model=settings.embedding_model,
    )
    reranker_backend = HarmonyRerankerBackend(model=pipeline_config.reranker_model)
    return SearchService(
        keyword_backend=keyword_backend,
        vector_backend=vector_backend,
        reranker_backend=reranker_backend,
        config=pipeline_config,
    ), keyword_backend


@asynccontextmanager
async def lifespan(app: FastAPI) -> typing.AsyncGenerator[None, None]:
    """
    Lifespan context manager for FastAPI application.

    Handles startup and shutdown logic:
    - Startup: Initialize services, tools, and connections
    - Shutdown: Clean up resources and close connections
    """
    logger.info("Starting Harmony API...")

    prompts_dir = settings.prompts_dir or Path(__file__).parent.parent / "prompts"
    initialize_prompt_manager(
        templates_dir=prompts_dir,
        auto_reload=settings.dev_mode,
    )
    logger.info(f"Initialized prompt manager with templates from {prompts_dir}")

    if await es_service.health_check():
        logger.info(f"Connected to Elasticsearch at {settings.es_config.host}")
    else:
        logger.error(f"Failed to connect to Elasticsearch at {settings.es_config.host}")

    qdrant_service = QdrantService(
        host=settings.qdrant_host,
        collection=settings.qdrant_collection,
        vector_size=settings.qdrant_vector_size,
    )
    await qdrant_service.ensure_collection()
    logger.info(f"Connected to Qdrant at {settings.qdrant_host}")

    # TODO: load pipeline_config from persistent store (DB) when available
    pipeline_config = PipelineConfig()
    app.state.pipeline_config = pipeline_config

    search_service, keyword_backend = _build_search_service(
        qdrant_service, pipeline_config
    )
    app.state.search_service = search_service
    search_module.search_service = search_service
    logger.info("SearchService initialized with pipeline config: %s", pipeline_config)

    if settings.document_cache_enabled:
        document_cache.ttl = float(settings.document_cache_ttl)
        document_cache.max_size = settings.document_cache_max_size
        logger.info(
            f"Document cache enabled: TTL={settings.document_cache_ttl}s, "
            f"max_size={settings.document_cache_max_size}"
        )

    tool_registry.register(search_documents_tool)  # type: ignore[arg-type]
    tool_registry.register(get_document_details_tool)  # type: ignore[arg-type]
    tool_registry.register(fetch_url_tool)  # type: ignore[arg-type]
    tool_registry.register(fetch_pdf_tool)  # type: ignore[arg-type]
    tool_registry.register(fetch_document_tool)  # type: ignore[arg-type]

    logger.info(
        f"Registered {len(tool_registry.tools)} built-in tools: {list(tool_registry.tools.keys())}"
    )

    if settings.mcp_servers:
        logger.info(f"Loading {len(settings.mcp_servers)} MCP servers...")
        app.state.mcp_loader = MCPServerLoader(settings.mcp_servers)
        await app.state.mcp_loader.load_servers()

        for mcp_tool in app.state.mcp_loader.get_tools():
            tool_registry.register(mcp_tool)

        logger.info(
            f"Registered {len(app.state.mcp_loader.get_tools())} MCP tools. "
            f"Total tools: {len(tool_registry.tools)}"
        )
    else:
        app.state.mcp_loader = None
        logger.info("No MCP servers configured")

    logger.info("Harmony API startup complete")

    yield

    logger.info("Shutting down Harmony API...")

    await es_service.close()
    logger.info("Closed Elasticsearch connection")

    await qdrant_service.close()
    logger.info("Closed Qdrant connection")
    await keyword_backend.close()

    if hasattr(app.state, "mcp_loader") and app.state.mcp_loader:
        await app.state.mcp_loader.cleanup()
        logger.info("Cleaned up MCP servers")

    logger.info("Harmony API shutdown complete")


app = FastAPI(
    title="Harmony API",
    description="LLM-powered information retrieval system",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for Open WebUI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify Open WebUI domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(search.router)
app.include_router(chat.router)
app.include_router(agentic_search.router)
app.include_router(settings_route.router)


@app.get("/")
async def root() -> dict[str, str | dict[str, str]]:
    """Root endpoint."""
    return {
        "name": "Harmony API",
        "version": "0.1.0",
        "endpoints": {
            "search": "/search?q=your_query",
            "ai_search": "/ai-search (POST)",
            "agentic_search": "/agentic-search (POST)",
            "docs": "/docs",
        },
    }


async def _check_ollama_health() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{settings.ollama_host}/")
            return "Ollama is" in response.text
    except Exception:
        return False


@app.get("/health")
async def health() -> dict[str, str | bool]:
    """Health check endpoint."""
    es_healthy = await es_service.health_check()
    ollama_healthy = await _check_ollama_health()
    all_healthy = es_healthy and ollama_healthy
    return {
        "status": "healthy" if all_healthy else "degraded",
        "elasticsearch": es_healthy,
        "ollama": ollama_healthy,
    }


def run() -> None:
    """Run the API server."""
    uvicorn.run(
        "harmony.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )


if __name__ == "__main__":
    run()
