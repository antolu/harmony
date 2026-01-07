from __future__ import annotations

import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from harmony.api.config import settings
from harmony.api.routes import agentic_search, chat, search
from harmony.api.services.elasticsearch import es_service
from harmony.api.tools.documents import (
    fetch_document_tool,
    fetch_pdf_tool,
    fetch_url_tool,
)
from harmony.api.tools.registry import tool_registry
from harmony.api.tools.search import get_document_details_tool, search_documents_tool

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Harmony API",
    description="LLM-powered information retrieval system",
    version="0.1.0",
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


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize services and tool registry on startup."""
    # Check Elasticsearch connection
    if await es_service.health_check():
        logger.info(f"Connected to Elasticsearch at {settings.es_host}")
    else:
        logger.error(f"Failed to connect to Elasticsearch at {settings.es_host}")

    # Register built-in tools
    tool_registry.register(search_documents_tool)
    tool_registry.register(get_document_details_tool)
    tool_registry.register(fetch_url_tool)
    tool_registry.register(fetch_pdf_tool)
    tool_registry.register(fetch_document_tool)

    logger.info(
        f"Registered {len(tool_registry.tools)} tools: {list(tool_registry.tools.keys())}"
    )


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Close connections on shutdown."""
    await es_service.close()


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
