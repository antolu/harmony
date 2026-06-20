from __future__ import annotations

import dataclasses
import os
import typing
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import httpx
import litellm
import starlette.datastructures
import structlog
import uvicorn
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key,
    load_pem_public_key,
)
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from harmony.api.admin_config import settings as admin_settings
from harmony.api.agents import (
    AgenticOrchestrator,
    AgentSuite,
    CriticAgent,
    QueryPlannerAgent,
    SearcherAgent,
    SynthesizerAgent,
)
from harmony.api.auth.middleware import JWTAuthMiddleware, generate_rsa_key_pair
from harmony.api.backends import (
    HarmonyKeywordBackend,
    HarmonyRerankerBackend,
    HarmonyVectorBackend,
)
from harmony.api.config import settings
from harmony.api.observability import (
    TraceMiddleware,
    UsageCallback,
    configure_logging,
    start_queue_consumer,
)
from harmony.api.observability._secret_service import SecretValueService
from harmony.api.routes import agentic_search, chat, search, user_auth
from harmony.api.routes import conversations as conversations_route
from harmony.api.routes import feedback as feedback_route
from harmony.api.routes import preferences as preferences_route
from harmony.api.routes import settings as settings_route
from harmony.api.routes.admin import (
    _crawler_sessions,
    _infrastructure,
    _safety,
    _signals,
    _stats,
    _webhook_internal,
    auth,
    configs,
    data_sources,
    index_config,
    jobs,
    logs,
    ollama,
    reset,
    schema,
    setup,
)
from harmony.api.routes.admin import (
    audit_log as audit_log_route,
)
from harmony.api.routes.admin import (
    export as export_route,
)
from harmony.api.routes.admin import (
    external_providers as external_providers_route,
)
from harmony.api.routes.admin import (
    model_policy as model_policy_route,
)
from harmony.api.routes.admin import (
    model_settings as model_settings_route,
)
from harmony.api.routes.admin import (
    schedules as schedules_route,
)
from harmony.api.routes.admin import (
    token_usage as token_usage_route,
)
from harmony.api.routes.admin import (
    urls as urls_route,
)
from harmony.api.routes.admin import (
    users as users_route,
)
from harmony.api.routes.admin import (
    webhooks as webhooks_route,
)
from harmony.api.services import (
    ConversationService,
    DocumentCache,
    ElasticsearchService,
    ExternalSearchService,
    LLMService,
    PipelineConfig,
    PromptManager,
    QdrantService,
    SearchService,
)
from harmony.api.services.admin import (
    AuditLogService,
    CrawlConfigService,
    IndexerConfigService,
    JobManager,
    LogStreamer,
    ModelPolicyStore,
    ModelRegistryService,
    ModelSettingsStore,
    ScheduleService,
    ServiceConfigStore,
    WebhookService,
)
from harmony.api.services.admin import (
    config_store as _config_store_singleton,
)
from harmony.api.services.admin._data_sources import DataSourcesService
from harmony.api.services.admin._export_service import ExportService
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
from harmony.db.redis_client import get_async_redis
from harmony.db.repositories import CrawlBlacklistRepo, JobLogsRepo
from harmony.providers import ProviderRegistry

logger = structlog.get_logger(__name__)


async def _load_pipeline_config(service_config: ServiceConfigStore) -> PipelineConfig:
    def _int(val: str | None, default: int) -> int:
        try:
            return int(val) if val else default
        except ValueError:
            return default

    def _bool(val: str | None, *, default: bool) -> bool:
        if not val:
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


async def _init_db(app: FastAPI) -> None:
    if settings.gemini_api_key:
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
    pool = await get_async_pool()
    logger.info("Connected to PostgreSQL")

    service_config = ServiceConfigStore()
    await service_config.initialize(pool)
    app.state.service_config_store = service_config
    app.state.db_pool = pool

    model_settings_store = ModelSettingsStore()
    app.state.model_settings_store = model_settings_store

    secret_service = await SecretValueService.from_env_or_db(service_config)
    app.state.secret_service = secret_service

    model_policy_store = ModelPolicyStore(pool)
    app.state.model_policy_store = model_policy_store

    ollama_host = await service_config.get("ollama_host")
    if ollama_host:
        os.environ["OLLAMA_API_BASE"] = ollama_host
        logger.info(f"Set OLLAMA_API_BASE={ollama_host}")

    config_status = await service_config.get_status()
    logger.info(f"Service configuration: {config_status}")


async def _init_search_service(app: FastAPI) -> None:  # noqa: PLR0914
    pool = app.state.db_pool
    service_config: ServiceConfigStore = app.state.service_config_store
    model_settings_store: ModelSettingsStore = app.state.model_settings_store

    es_url = await service_config.get("elasticsearch_url")
    es_service = ElasticsearchService(host=es_url)
    if await es_service.health_check():
        logger.info(f"Connected to Elasticsearch at {es_url}")
    else:
        logger.error(f"Failed to connect to Elasticsearch at {es_url}")
    app.state.es_service = es_service

    qdrant_service: QdrantService | None = None
    try:
        qdrant_service = QdrantService(
            host=settings.qdrant_host,
            collection=settings.qdrant_collection,
        )
        await qdrant_service.ensure_collection()
        logger.info(f"Connected to Qdrant at {settings.qdrant_host}")
    except Exception:
        logger.warning("Qdrant unavailable — vector search disabled")
        qdrant_service = None
    app.state.qdrant_service = qdrant_service

    llm_service = LLMService(
        service_config=service_config,
        model_settings_store=model_settings_store,
        model_policy_store=app.state.model_policy_store,
    )
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

    pipeline_config = await _load_pipeline_config(service_config)
    if qdrant_service is None or await qdrant_service.is_empty():
        pipeline_config = dataclasses.replace(
            pipeline_config, vector_search_enabled=False
        )
        if qdrant_service is not None:
            logger.info(
                "Qdrant collection empty — vector search disabled until first embed job"
            )
    app.state.pipeline_config = pipeline_config

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
        service_config=service_config,
        model_settings_store=model_settings_store,
    )
    reranker_backend = HarmonyRerankerBackend(
        service_config=service_config,
        model_settings_store=model_settings_store,
    )
    external_search_service = ExternalSearchService(
        service_config=service_config,
        secret_service=app.state.secret_service,
    )
    app.state.external_search_service = external_search_service
    search_service = SearchService(
        keyword_backend=keyword_backend,
        vector_backend=vector_backend,
        reranker_backend=reranker_backend,
        config=pipeline_config,
        external_search_service=external_search_service,
    )
    app.state.search_service = search_service
    app.state.keyword_backend = keyword_backend
    logger.info("SearchService initialized with pipeline config: %s", pipeline_config)


def _init_tool_registry(app: FastAPI) -> None:
    es_service: ElasticsearchService = app.state.es_service
    search_service: SearchService = app.state.search_service
    document_cache: DocumentCache = app.state.document_cache

    tool_registry = ToolRegistry()
    tool_registry.register(SearchDocumentsTool(search_service=search_service))
    tool_registry.register(GetDocumentDetailsTool(es_service=es_service))
    tool_registry.register(FetchURLTool(document_cache=document_cache))
    tool_registry.register(FetchPDFTool(document_cache=document_cache))
    tool_registry.register(FetchDocumentTool(document_cache=document_cache))
    app.state.tool_registry = tool_registry
    logger.info(f"Registered {len(tool_registry.tools)} built-in tools")


async def _init_mcp_servers(app: FastAPI) -> None:
    tool_registry: ToolRegistry = app.state.tool_registry

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


async def _init_auth(app: FastAPI) -> None:
    service_config: ServiceConfigStore = app.state.service_config_store
    private_pem = await service_config.get("jwt_private_key_pem")
    public_pem = await service_config.get("jwt_public_key_pem")
    if not private_pem or not public_pem:
        private_pem, public_pem = generate_rsa_key_pair()
        await service_config.set("jwt_private_key_pem", private_pem, validated=True)
        await service_config.set("jwt_public_key_pem", public_pem, validated=True)
        logger.info("Generated new RSA key pair for JWT signing")
    app.state.jwt_private_key = load_pem_private_key(
        private_pem.encode(), password=None, backend=default_backend()
    )
    app.state.jwt_public_key = load_pem_public_key(
        public_pem.encode(), backend=default_backend()
    )
    auth_mode = await service_config.get("auth_mode") or "optional"
    app.state.auth_mode = auth_mode
    app.state.harmony_public_url = await service_config.get("harmony_public_url") or ""
    redis_client = await get_async_redis()
    app.state.redis_client = redis_client
    logger.info(f"JWT authentication initialized (auth_mode={auth_mode})")


async def _init_admin_services(app: FastAPI) -> None:
    admin_settings.config_storage_path.mkdir(parents=True, exist_ok=True)
    admin_settings.job_log_path.mkdir(parents=True, exist_ok=True)

    _config_store_singleton.initialize(admin_settings.config_storage_path)
    app.state.config_store = _config_store_singleton

    job_manager = JobManager()
    await job_manager.initialize(job_log_path=admin_settings.job_log_path)
    app.state.job_manager = job_manager

    app.state.log_streamer = LogStreamer()

    pool = app.state.db_pool

    crawl_config_service = CrawlConfigService()
    await crawl_config_service.initialize(pool)
    await crawl_config_service.import_from_filesystem(
        admin_settings.config_storage_path / "crawler",
        created_by=None,
    )
    app.state.crawl_config_service = crawl_config_service

    app.state.provider_registry = ProviderRegistry()
    data_sources_service = DataSourcesService()
    await data_sources_service.initialize(pool)
    app.state.data_sources_service = data_sources_service
    await data_sources_service.promote_crawler_configs(crawl_config_service)

    indexer_config_service = IndexerConfigService()
    await indexer_config_service.initialize(pool)
    await indexer_config_service.import_from_filesystem_if_empty(
        admin_settings.config_storage_path / "indexer"
    )
    app.state.indexer_config_service = indexer_config_service

    audit_log_service = AuditLogService()
    await audit_log_service.initialize(pool)
    app.state.audit_log_service = audit_log_service

    model_registry_service = ModelRegistryService()
    await model_registry_service.initialize(
        pool, audit_log_service, app.state.secret_service
    )
    app.state.model_registry_service = model_registry_service
    app.state.llm_service.set_model_registry(model_registry_service)

    db_url = os.environ.get("DATABASE_URL", "")
    schedule_service = ScheduleService()
    if db_url:
        await schedule_service.initialize(db_url=db_url)
        await schedule_service.add_nightly_job(
            "audit_log_cleanup",
            func=lambda: nightly_audit_cleanup(app.state),
            hour=2,
        )
        await schedule_service.add_nightly_job(
            "conversation_ttl_cleanup",
            func=lambda: nightly_conversation_cleanup(app.state),
            hour=3,
        )
    app.state.schedule_service = schedule_service

    webhook_service = WebhookService()
    await webhook_service.initialize(pool, audit_log_service)
    webhook_service.set_secret_service(app.state.secret_service)
    app.state.webhook_service = webhook_service
    job_manager.set_webhook_service(webhook_service)
    job_manager.set_config_services(
        crawl_config_service,
        indexer_config_service,
        app.state.model_settings_store,
    )

    app.state.crawl_blacklist_repo = CrawlBlacklistRepo(pool)
    app.state.job_logs_repo = JobLogsRepo(pool)

    export_service = ExportService(
        app.state.es_service,
        app.state.qdrant_service,
        audit_log_service,
    )
    app.state.export_service = export_service


def _init_orchestrator(app: FastAPI) -> None:
    llm_service: LLMService = app.state.llm_service
    prompt_manager: PromptManager = app.state.prompt_manager
    search_service: SearchService = app.state.search_service
    pipeline_config = app.state.pipeline_config

    agents = AgentSuite(
        query_planner=QueryPlannerAgent(
            llm_service=llm_service, prompt_manager=prompt_manager
        ),
        searcher=SearcherAgent(search_service=search_service),
        critic=CriticAgent(llm_service=llm_service, prompt_manager=prompt_manager),
        synthesizer=SynthesizerAgent(
            llm_service=llm_service, prompt_manager=prompt_manager
        ),
    )
    orchestrator = AgenticOrchestrator(
        agents=agents,
        max_refinement_rounds=pipeline_config.agentic_max_refinement_rounds,
        max_query_variants=pipeline_config.agentic_max_query_variants,
    )
    app.state.orchestrator = orchestrator


async def nightly_audit_cleanup(
    app_state: starlette.datastructures.State,
) -> None:
    service_config: ServiceConfigStore = app_state.service_config_store
    audit_log_service: AuditLogService = app_state.audit_log_service
    retention_days_str = await service_config.get("audit_retention_days")
    try:
        retention_days = int(retention_days_str) if retention_days_str else 90
    except ValueError:
        retention_days = 90
    deleted = await audit_log_service.cleanup_audit_events(retention_days)
    logger.info(
        f"Nightly audit cleanup: removed {deleted} records older than {retention_days} days"
    )


async def nightly_conversation_cleanup(
    app_state: starlette.datastructures.State,
) -> None:
    service_config: ServiceConfigStore = app_state.service_config_store
    pool = app_state.db_pool
    ttl_days_str = await service_config.get("conversation_ttl_days")
    try:
        ttl_days = int(ttl_days_str) if ttl_days_str else 0
    except ValueError:
        ttl_days = 0
    if ttl_days > 0:
        async with pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM conversations WHERE created_at < now() - interval '1 day' * %s",
                    (ttl_days,),
                )
                deleted = cur.rowcount
        logger.info(
            f"Nightly conversation cleanup: removed {deleted} conversations older than {ttl_days} days"
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> typing.AsyncGenerator[None, None]:
    configure_logging(dev_mode=settings.dev_mode)
    usage_callback = UsageCallback()
    litellm.callbacks.append(usage_callback)
    app.state.usage_callback = usage_callback
    app.state.token_consumer_task = None
    logger.info("Starting Harmony API...")

    if not settings.cors_allowed_origins:
        msg = "CORS_ALLOWED_ORIGINS must be set. Comma-separated list of allowed origins (e.g. http://localhost:3001,http://localhost:8080)."
        raise RuntimeError(msg)

    await _init_db(app)
    app.state.token_consumer_task = start_queue_consumer(
        queue=usage_callback.get_usage_queue(),
        pool=app.state.db_pool,
    )
    await _init_search_service(app)
    _init_tool_registry(app)
    await _init_mcp_servers(app)
    await _init_admin_services(app)
    await _init_auth(app)
    _init_orchestrator(app)

    logger.info("Harmony API startup complete")

    try:
        yield
    finally:
        logger.info("Shutting down Harmony API...")

        if app.state.token_consumer_task is not None:
            app.state.token_consumer_task.cancel()
            with suppress(Exception):
                await app.state.token_consumer_task

        await app.state.es_service.close()
        if app.state.qdrant_service is not None:
            await app.state.qdrant_service.close()
        await app.state.keyword_backend.close()

        if app.state.mcp_loader:
            await app.state.mcp_loader.cleanup()

        await app.state.job_manager.cleanup()
        await app.state.schedule_service.shutdown()
        await close_async_pool()

        logger.info("Harmony API shutdown complete")


app = FastAPI(
    title="Harmony API",
    description="LLM-powered information retrieval system",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Unhandled exception", method=request.method, path=request.url.path
    )
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc) or "Internal server error"},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(JWTAuthMiddleware)
app.add_middleware(TraceMiddleware)

app.include_router(search.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(agentic_search.router, prefix="/api")
app.include_router(settings_route.router, prefix="/api")

app.include_router(user_auth.router, prefix="/api", tags=["user-auth"])
app.include_router(schema.router, prefix="/api/admin/configs", tags=["schema"])
app.include_router(configs.router, prefix="/api/admin/configs", tags=["configs"])
app.include_router(
    data_sources.router, prefix="/api/admin/data-sources", tags=["admin"]
)
app.include_router(jobs.router, prefix="/api/admin/jobs", tags=["jobs"])
app.include_router(logs.router, prefix="/api/admin/jobs", tags=["logs"])
app.include_router(reset.router, prefix="/api/reset", tags=["reset"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(_safety.router, prefix="/api/internal", tags=["internal"])
app.include_router(_crawler_sessions.router, prefix="/api/internal", tags=["internal"])
app.include_router(_stats.router, prefix="/api/internal", tags=["internal"])
app.include_router(_signals.router, prefix="/api/internal", tags=["internal"])
app.include_router(_webhook_internal.router, prefix="/api/internal", tags=["internal"])
app.include_router(setup.router, prefix="/api/setup", tags=["setup"])
app.include_router(
    index_config.router, prefix="/api/index-config", tags=["index-config"]
)
app.include_router(ollama.router, prefix="/api/admin/models/ollama", tags=["ollama"])
app.include_router(
    model_settings_route.router, prefix="/api/admin/models", tags=["model-settings"]
)
app.include_router(token_usage_route.router, prefix="/api/admin", tags=["token-usage"])
app.include_router(urls_route.router, prefix="/api")
app.include_router(users_route.router, prefix="/api")
app.include_router(
    model_policy_route.router, prefix="/api/settings", tags=["model-policy"]
)
app.include_router(
    external_providers_route.router, prefix="/api/settings", tags=["external-providers"]
)
app.include_router(_infrastructure.router, prefix="/api", tags=["admin"])
app.include_router(
    conversations_route.router, prefix="/api/conversations", tags=["conversations"]
)
app.include_router(feedback_route.router, prefix="/api/feedback", tags=["feedback"])
app.include_router(
    preferences_route.router, prefix="/api/preferences", tags=["preferences"]
)
app.include_router(audit_log_route.router, prefix="/api")
app.include_router(webhooks_route.router, prefix="/api")
app.include_router(schedules_route.router, prefix="/api")
app.include_router(export_route.router, prefix="/api")


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
    except Exception as exc:
        logger.warning("readiness_check_failed", dep="ollama", error=str(exc))
        return False


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — always returns ok if the process is alive."""
    return {"status": "ok"}


@app.get("/api/health")
async def api_health() -> dict[str, str]:
    """Liveness probe (api prefix) — always returns ok if the process is alive."""
    return {"status": "ok"}


async def _check_deps() -> dict[str, bool | str]:
    deps: dict[str, bool | str] = {}

    try:
        es_healthy = await app.state.es_service.health_check()
    except Exception as exc:
        logger.warning("readiness_check_failed", dep="elasticsearch", error=str(exc))
        es_healthy = False
    deps["elasticsearch"] = es_healthy

    try:
        async with app.state.db_pool.connection() as _:
            pass
        deps["postgres"] = True
    except Exception as exc:
        logger.warning("readiness_check_failed", dep="postgres", error=str(exc))
        deps["postgres"] = False

    deps["redis"] = await _check_redis()

    qdrant = getattr(app.state, "qdrant_service", None)
    if qdrant is None:
        deps["qdrant"] = "disabled"
    else:
        try:
            deps["qdrant"] = not await qdrant.is_empty() or True
        except Exception as exc:
            logger.warning("readiness_check_failed", dep="qdrant", error=str(exc))
            deps["qdrant"] = False

    if settings.ollama_host:
        deps["ollama"] = await _check_ollama_health()
    else:
        deps["ollama"] = "disabled"

    return deps


async def _check_redis() -> bool:
    redis = getattr(app.state, "redis_client", None)
    if redis is None:
        return False
    try:
        await redis.ping()
    except Exception as exc:
        logger.warning("readiness_check_failed", dep="redis", error=str(exc))
        return False
    else:
        return True


@app.get("/ready")
async def ready() -> Response:
    """Readiness probe — checks all configured dependencies."""
    deps = await _check_deps()
    required = ["elasticsearch", "postgres", "redis"]
    all_ready = all(deps[k] is True for k in required)
    status = "ready" if all_ready else "degraded"
    content: dict[str, str | dict[str, bool | str]] = {
        "status": status,
        "dependencies": deps,
    }
    status_code = 200 if all_ready else 503
    return JSONResponse(status_code=status_code, content=content)


@app.get("/api/ready")
async def api_ready() -> Response:
    """Readiness probe (api prefix) — checks all configured dependencies."""
    return await ready()


def run() -> None:
    uvicorn.run(
        "harmony.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )


if __name__ == "__main__":
    run()
