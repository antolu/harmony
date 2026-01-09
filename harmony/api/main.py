from __future__ import annotations

import logging
import typing
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from harmony.api.config import settings
from harmony.api.routes import agentic_search, chat, search
from harmony.api.services.document_cache import document_cache
from harmony.api.services.elasticsearch import es_service
from harmony.api.services.prompts import initialize_prompt_manager
from harmony.api.tools.documents import (
    fetch_document_tool,
    fetch_pdf_tool,
    fetch_url_tool,
)
from harmony.api.tools.mcp import MCPServerLoader
from harmony.api.tools.registry import tool_registry
from harmony.api.tools.search import get_document_details_tool, search_documents_tool

logger = logging.getLogger(__name__)


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


@app.get("/health")
async def health() -> dict[str, str | bool]:
    """Health check endpoint."""
    es_healthy = await es_service.health_check()
    return {
        "status": "healthy" if es_healthy else "unhealthy",
        "elasticsearch": es_healthy,
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
