from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from harmony.api.config import settings
from harmony.api.routes import chat, search
from harmony.api.services.elasticsearch import es_service

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


@app.on_event("startup")
async def startup_event() -> None:
    """Verify connections on startup."""
    # Check Elasticsearch connection
    if await es_service.health_check():
        print(f"✓ Connected to Elasticsearch at {settings.es_host}")
    else:
        print(f"✗ Failed to connect to Elasticsearch at {settings.es_host}")


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
