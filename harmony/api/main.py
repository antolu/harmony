from __future__ import annotations

import dataclasses
import logging
import os
import typing
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from harmony.api.admin_config import settings as admin_settings
from harmony.api.backends import (
    HarmonyKeywordBackend,
    HarmonyRerankerBackend,
    HarmonyVectorBackend,
)
from harmony.api.config import settings
from harmony.api.routes import agentic_search, chat, search
from harmony.api.routes import settings as settings_route
from harmony.api.routes.admin import (
    _crawler_sessions,
    _infrastructure,
    _safety,
    _signals,
    _stats,
    auth,
    configs,
    index_config,
    jobs,
    logs,
    ollama,
    reset,
    schema,
    setup,
)
from harmony.api.routes.admin import (
    model_settings as model_settings_route,
)
from harmony.api.services import (
    ConversationService,
    DocumentCache,
    ElasticsearchService,
    LLMService,
    PipelineConfig,
    PromptManager,
    QdrantService,
    SearchService,
)
from harmony.api.services.admin import (
    ConfigStore,
    JobManager,
    LogStreamer,
    ModelSettingsStore,
    ServiceConfigStore,
    SSOHandler,
)
from harmony.api.tools import (
    FetchDocumentTool,
    FetchPDFTool,
    FetchURLTool,
    GetDocumentDetailsTool,
    MCPServerLoader,
    SearchDocumentsTool,
    ToolRegistry,
)
from harmony.db.connection import close_async_pool, get_async_pool

logger = logging.getLogger(__name__)


async def _load_pipeline_config(service_config: ServiceConfigStore) -> PipelineConfig:
    def _int(val: str | None, default: int) -> int:
        try:
            return int(val) if val else default
        except ValueError:
            return default

    def _bool(val: str | None, *, default: bool) -> bool:
        if val is None:
            return default
        return val.lower() in {"true", "1", "yes"}

    return PipelineConfig(
        keyword_candidates_n=_int(
            await service_config.get("pipeline_keyword_candidates_n"), 50
        ),
        vector_top_k=_int(await service_config.get("pipeline_vector_top_k"), 20),
        search_top_k=_int(await service_config.get("pipeline_search_top_k"), 5),
        vector_search_enabled=_bool(
            await service_config.get("pipeline_vector_search_enabled"), default=True
        ),
        reranker_enabled=_bool(
            await service_config.get("pipeline_reranker_enabled"), default=False
        ),
        agentic_max_refinement_rounds=_int(
            await service_config.get("pipeline_agentic_max_refinement_rounds"), 3
        ),
        agentic_max_query_variants=_int(
            await service_config.get("pipeline_agentic_max_query_variants"), 4
        ),
        agentic_search_top_k=_int(
            await service_config.get("pipeline_agentic_search_top_k"), 10
        ),
        agentic_max_sources_returned=_int(
            await service_config.get("pipeline_agentic_max_sources_returned"), 10
        ),
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> typing.AsyncGenerator[None, None]:  # noqa: PLR0915,PLR0914
    logger.info("Starting Harmony API...")

    # Apply LLM provider env vars before constructing LLMService
    if settings.gemini_api_key:
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
    if settings.llm_model.startswith("ollama_chat/"):
        os.environ["OLLAMA_API_BASE"] = settings.ollama_host

    # DB pool
    pool = await get_async_pool()
    logger.info("Connected to PostgreSQL")

    # Infrastructure config from DB
    service_config = ServiceConfigStore()
    await service_config.initialize(pool)
    app.state.service_config_store = service_config

    config_status = await service_config.get_status()
    logger.info(f"Service configuration: {config_status}")

    # Core services
    es_url = await service_config.get("elasticsearch_url")
    es_service = ElasticsearchService(host=es_url)
    if await es_service.health_check():
        logger.info(f"Connected to Elasticsearch at {es_url}")
    else:
        logger.error(f"Failed to connect to Elasticsearch at {es_url}")
    app.state.es_service = es_service

    qdrant_service = QdrantService(
        host=settings.qdrant_host,
        collection=settings.qdrant_collection,
        vector_size=settings.qdrant_vector_size,
    )
    await qdrant_service.ensure_collection()
    logger.info(f"Connected to Qdrant at {settings.qdrant_host}")

    llm_service = LLMService()
    app.state.llm_service = llm_service

    prompts_dir = settings.prompts_dir or Path(__file__).parent.parent / "prompts"
    prompt_manager = PromptManager(
        templates_dir=prompts_dir,
        auto_reload=settings.dev_mode,
    )
    app.state.prompt_manager = prompt_manager
    logger.info(f"Initialized prompt manager with templates from {prompts_dir}")

    document_cache = DocumentCache(
        ttl=settings.document_cache_ttl if settings.document_cache_enabled else 3600,
        max_size=settings.document_cache_max_size
        if settings.document_cache_enabled
        else 1000,
    )
    if settings.document_cache_enabled:
        logger.info(
            f"Document cache enabled: TTL={settings.document_cache_ttl}s, "
            f"max_size={settings.document_cache_max_size}"
        )
    app.state.document_cache = document_cache

    conversation_service = ConversationService(pool=pool)
    app.state.conversation_service = conversation_service

    # Pipeline config (load from DB, fall back to defaults)
    pipeline_config = await _load_pipeline_config(service_config)
    if await qdrant_service.is_empty():
        pipeline_config = dataclasses.replace(
            pipeline_config, vector_search_enabled=False
        )
        logger.info(
            "Qdrant collection empty — vector search disabled until first embed job"
        )
    app.state.pipeline_config = pipeline_config

    # Search service
    keyword_backend = HarmonyKeywordBackend(
        host=settings.es_config.host,
        index_base_name=settings.es_config.index_base_name,
        languages=settings.es_config.languages,
        boost_title=settings.es_config.mutable.boost_title,
        boost_content=settings.es_config.mutable.boost_content,
        size=pipeline_config.keyword_candidates_n,
    )
    vector_backend = HarmonyVectorBackend(qdrant_service=qdrant_service)
    reranker_backend = HarmonyRerankerBackend()
    search_service = SearchService(
        keyword_backend=keyword_backend,
        vector_backend=vector_backend,
        reranker_backend=reranker_backend,
        config=pipeline_config,
    )
    app.state.search_service = search_service
    logger.info("SearchService initialized with pipeline config: %s", pipeline_config)

    # Tool registry
    tool_registry = ToolRegistry()
    tool_registry.register(SearchDocumentsTool(search_service=search_service))
    tool_registry.register(GetDocumentDetailsTool(es_service=es_service))
    tool_registry.register(FetchURLTool(document_cache=document_cache))
    tool_registry.register(FetchPDFTool(document_cache=document_cache))
    tool_registry.register(FetchDocumentTool(document_cache=document_cache))
    app.state.tool_registry = tool_registry
    logger.info(f"Registered {len(tool_registry.tools)} built-in tools")

    # MCP servers
    if settings.mcp_servers:
        logger.info(f"Loading {len(settings.mcp_servers)} MCP servers...")
        mcp_loader = MCPServerLoader(settings.mcp_servers)
        await mcp_loader.load_servers()
        for mcp_tool in mcp_loader.get_tools():
            tool_registry.register(mcp_tool)
        app.state.mcp_loader = mcp_loader
        logger.info(f"Registered {len(mcp_loader.get_tools())} MCP tools")
    else:
        app.state.mcp_loader = None
        logger.info("No MCP servers configured")

    # Admin services
    admin_settings.config_storage_path.mkdir(parents=True, exist_ok=True)
    admin_settings.job_log_path.mkdir(parents=True, exist_ok=True)

    config_store = ConfigStore()
    config_store.initialize(admin_settings.config_storage_path)
    app.state.config_store = config_store

    job_manager = JobManager()
    await job_manager.initialize(job_log_path=admin_settings.job_log_path)
    app.state.job_manager = job_manager

    app.state.log_streamer = LogStreamer()
    app.state.model_settings_store = ModelSettingsStore()
    app.state.sso_handler = SSOHandler()

    # Agentic orchestrator (must come after search_service and prompt_manager)
    from harmony.api.agents import (  # noqa: PLC0415
        AgenticOrchestrator,
        CriticAgent,
        QueryPlannerAgent,
        SearcherAgent,
        SynthesizerAgent,
    )

    orchestrator = AgenticOrchestrator(
        query_planner=QueryPlannerAgent(
            llm_service=llm_service, prompt_manager=prompt_manager
        ),
        searcher=SearcherAgent(search_service=search_service),
        critic=CriticAgent(llm_service=llm_service, prompt_manager=prompt_manager),
        synthesizer=SynthesizerAgent(
            llm_service=llm_service, prompt_manager=prompt_manager
        ),
        max_refinement_rounds=pipeline_config.agentic_max_refinement_rounds,
        max_query_variants=pipeline_config.agentic_max_query_variants,
    )
    app.state.orchestrator = orchestrator

    logger.info("Harmony API startup complete")

    yield

    logger.info("Shutting down Harmony API...")

    await es_service.close()
    await qdrant_service.close()
    await keyword_backend.close()

    if app.state.mcp_loader:
        await app.state.mcp_loader.cleanup()

    await job_manager.cleanup()
    await close_async_pool()

    logger.info("Harmony API shutdown complete")


app = FastAPI(
    title="Harmony API",
    description="LLM-powered information retrieval system",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router)
app.include_router(chat.router)
app.include_router(agentic_search.router)
app.include_router(settings_route.router)

app.include_router(schema.router, prefix="/api/configs", tags=["schema"])
app.include_router(configs.router, prefix="/api/configs", tags=["configs"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(logs.router, prefix="/api/jobs", tags=["logs"])
app.include_router(reset.router, prefix="/api/reset", tags=["reset"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(_safety.router, prefix="/api/internal", tags=["internal"])
app.include_router(_crawler_sessions.router, prefix="/api/internal", tags=["internal"])
app.include_router(_stats.router, prefix="/api/internal", tags=["internal"])
app.include_router(_signals.router, prefix="/api/internal", tags=["internal"])
app.include_router(setup.router, prefix="/api/setup", tags=["setup"])
app.include_router(
    index_config.router, prefix="/api/index-config", tags=["index-config"]
)
app.include_router(ollama.router, prefix="/api/models/ollama", tags=["ollama"])
app.include_router(
    model_settings_route.router, prefix="/api/settings/models", tags=["model-settings"]
)
app.include_router(_infrastructure.router, prefix="/api", tags=["admin"])


@app.get("/")
async def root() -> dict[str, str | dict[str, str]]:
    return {
        "name": "Harmony API",
        "version": "0.1.0",
        "endpoints": {
            "search": "/search?q=your_query",
            "ai_search": "/ai-search (POST)",
            "agentic_search": "/agentic-search (POST)",
            "admin": "/api",
            "docs": "/docs",
        },
    }


@app.get("/api")
async def api_root() -> dict[str, str | dict[str, str]]:
    return {
        "name": "Harmony Admin API",
        "version": "0.1.0",
        "endpoints": {
            "configs": "/api/configs",
            "jobs": "/api/jobs",
            "reset": "/api/reset",
            "auth": "/api/auth",
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
    try:
        es_healthy = await app.state.es_service.health_check()
    except AttributeError:
        es_healthy = False
    ollama_healthy = await _check_ollama_health()
    all_healthy = es_healthy and ollama_healthy
    return {
        "status": "healthy" if all_healthy else "degraded",
        "elasticsearch": es_healthy,
        "ollama": ollama_healthy,
    }


@app.get("/api/health")
async def api_health() -> dict[str, str | bool]:
    try:
        es_healthy = await app.state.es_service.health_check()
    except AttributeError:
        es_healthy = False
    return {
        "status": "healthy" if es_healthy else "unhealthy",
        "elasticsearch": es_healthy,
    }


def run() -> None:
    uvicorn.run(
        "harmony.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )


if __name__ == "__main__":
    run()
