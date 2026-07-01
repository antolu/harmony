from __future__ import annotations

import dataclasses
import os
import typing
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import litellm
import structlog
import uvicorn
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key,
    load_pem_public_key,
)
from fastapi import FastAPI
from psycopg_pool import AsyncConnectionPool

from harmony.agents import (
    AgenticOrchestrator,
    AgentSuite,
    CriticAgent,
    QueryPlannerAgent,
    SearcherAgent,
    SynthesizerAgent,
)
from harmony.api._middleware import apply_middlewares
from harmony.api._settings import load_pipeline_config
from harmony.api._state import AppState
from harmony.api.admin_config import settings as admin_settings
from harmony.api.auth.middleware import generate_rsa_key_pair
from harmony.api.config import Settings
from harmony.api.routes import router as api_router
from harmony.clients._elasticsearch import ElasticsearchService
from harmony.clients._qdrant import QdrantService
from harmony.db.connection import close_async_pool, get_async_pool
from harmony.db.redis_client import get_async_redis, get_sync_redis
from harmony.db.repositories import (
    CrawlBlacklistRepo,
    JobLogsRepo,
    LLMApiKeyRepo,
    ModelHostRepo,
    ModelRegistryRepo,
)
from harmony.infrastructure.search import (
    HarmonyKeywordBackend,
    HarmonyRerankerBackend,
    HarmonyVectorBackend,
    KeywordBackendConfig,
)
from harmony.observability import UsageCallback, configure_logging, start_queue_consumer
from harmony.providers import ProviderRegistry
from harmony.services import (
    ConversationService,
    DocumentCache,
    ExternalSearchService,
    LLMService,
    PromptManager,
    RedisDocumentCache,
    SearchService,
    SecretValueService,
    make_document_cache,
)
from harmony.services._pipeline_config import PipelineConfig
from harmony.services.admin import (
    AuditLogService,
    CrawlConfigService,
    IndexerConfigService,
    JobManager,
    LLMApiKeyService,
    LogStreamer,
    ModelHostService,
    ModelPolicyStore,
    ModelRegistryService,
    ModelSettingsStore,
    ScheduleService,
    ServiceConfigStore,
    WebhookService,
)
from harmony.services.admin import (
    config_store as _config_store_singleton,
)
from harmony.services.admin._data_sources import DataSourcesService
from harmony.services.admin._export_service import ExportService
from harmony.services.admin.jobs import (
    JobExecutor,
    KubernetesJobExecutor,
    SubprocessJobExecutor,
)
from harmony.tools import (
    FetchDocumentTool,
    FetchPDFTool,
    FetchURLTool,
    GetDocumentDetailsTool,
    SearchDocumentsTool,
    ToolRegistry,
)

logger = structlog.get_logger(__name__)


async def nightly_audit_cleanup() -> None:
    pool = await get_async_pool()
    service_config = ServiceConfigStore()
    await service_config.initialize(pool=pool)
    audit_svc = AuditLogService()
    await audit_svc.initialize(pool)
    retention_days_str = await service_config.get("audit_retention_days")
    try:
        retention_days = int(retention_days_str) if retention_days_str else 90
    except ValueError:
        retention_days = 90
    deleted = await audit_svc.cleanup_audit_events(retention_days)
    logger.info(
        f"Nightly audit cleanup: removed {deleted} records older than {retention_days} days"
    )


async def nightly_conversation_cleanup() -> None:
    pool = await get_async_pool()
    service_config = ServiceConfigStore()
    await service_config.initialize(pool=pool)
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


async def _init_db(settings: Settings) -> tuple:
    pool = await get_async_pool()
    logger.info("Connected to PostgreSQL")

    service_config = ServiceConfigStore()
    await service_config.initialize(pool)

    model_settings_store = ModelSettingsStore()

    secret_service = await SecretValueService.from_env_or_db(service_config)

    model_policy_store = ModelPolicyStore(pool)

    config_status = await service_config.get_status()
    logger.info(f"Service configuration: {config_status}")
    return (
        pool,
        service_config,
        model_settings_store,
        secret_service,
        model_policy_store,
    )


async def _init_storage_services(
    service_config: ServiceConfigStore, settings: Settings
) -> tuple:
    es_url = await service_config.get("elasticsearch_url")
    es_service = ElasticsearchService(host=es_url, es_config=settings.es_config)
    if await es_service.health_check():
        logger.info(f"Connected to Elasticsearch at {es_url}")
    else:
        logger.error(f"Failed to connect to Elasticsearch at {es_url}")

    qdrant_service = await QdrantService.create(
        service_config=service_config, collection=settings.qdrant_collection
    )
    return es_service, qdrant_service


async def _init_core_services(
    service_config: ServiceConfigStore,
    model_policy_store: ModelPolicyStore,
    pool: AsyncConnectionPool,
    settings: Settings,
) -> tuple:
    llm_service = LLMService(
        service_config=service_config,
        model_policy_store=model_policy_store,
    )

    prompts_dir = Path(__file__).parent.parent / "prompts"
    prompt_manager = PromptManager(
        templates_dir=prompts_dir,
        auto_reload=settings.dev_mode,
    )

    logger.info(f"Initialized prompt manager with templates from {prompts_dir}")

    cache_enabled = (
        await service_config.get("document_cache_enabled")
    ).lower() == "true"
    cache_ttl = int(await service_config.get("document_cache_ttl"))
    cache_max_size = int(await service_config.get("document_cache_max_size"))
    cache_backend = await service_config.get("document_cache_backend")

    cache_redis = await get_sync_redis() if cache_backend == "redis" else None
    document_cache = make_document_cache(
        cache_backend,
        redis=cache_redis,
        ttl=cache_ttl if cache_enabled else 3600,
        max_size=cache_max_size if cache_enabled else 1000,
    )
    if cache_enabled:
        logger.info(
            f"Document cache enabled: backend={cache_backend}, "
            f"TTL={cache_ttl}s, max_size={cache_max_size}"
        )

    conversation_service = ConversationService(pool=pool)
    return llm_service, prompt_manager, document_cache, conversation_service


async def _init_search_service(  # noqa: PLR0913
    service_config: ServiceConfigStore,
    model_settings_store: ModelSettingsStore,
    settings: Settings,
    qdrant_service: QdrantService | None,
    model_registry_service: ModelRegistryService,
    secret_service: SecretValueService,
) -> tuple:
    pipeline_config = await load_pipeline_config(service_config)
    if qdrant_service is None or await qdrant_service.is_empty():
        pipeline_config = dataclasses.replace(
            pipeline_config, vector_search_enabled=False
        )
        if qdrant_service is not None:
            logger.info(
                "Qdrant collection empty — vector search disabled until first embed job"
            )

    keyword_backend = HarmonyKeywordBackend(
        KeywordBackendConfig(
            host=settings.es_config.host,
            index_base_name=settings.es_config.index_base_name,
            languages=settings.es_config.languages,
            size=pipeline_config.keyword_candidates_n,
        ),
        service_config=service_config,
    )
    vector_backend = HarmonyVectorBackend(
        qdrant_service=qdrant_service,
        service_config=service_config,
        model_settings_store=model_settings_store,
        model_registry=model_registry_service,
    )
    reranker_backend = HarmonyRerankerBackend(
        service_config=service_config,
        model_settings_store=model_settings_store,
        model_registry=model_registry_service,
    )
    external_search_service = ExternalSearchService(
        service_config=service_config,
        secret_service=secret_service,
    )

    search_service = SearchService(
        keyword_backend=keyword_backend,
        vector_backend=vector_backend,
        reranker_backend=reranker_backend,
        config=pipeline_config,
        external_search_service=external_search_service,
    )
    logger.info("SearchService initialized with pipeline config: %s", pipeline_config)
    return pipeline_config, keyword_backend, external_search_service, search_service


def _init_tool_registry(
    es_service: ElasticsearchService,
    search_service: SearchService,
    document_cache: DocumentCache | RedisDocumentCache,
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


async def _init_auth(service_config: ServiceConfigStore) -> tuple:
    private_pem = await service_config.get("jwt_private_key_pem")
    public_pem = await service_config.get("jwt_public_key_pem")
    if not private_pem or not public_pem:
        private_pem, public_pem = generate_rsa_key_pair()
        await service_config.set("jwt_private_key_pem", private_pem, validated=True)
        await service_config.set("jwt_public_key_pem", public_pem, validated=True)
        logger.info("Generated new RSA key pair for JWT signing")
    jwt_private_key = load_pem_private_key(
        private_pem.encode(), password=None, backend=default_backend()
    )
    jwt_public_key = load_pem_public_key(public_pem.encode(), backend=default_backend())
    auth_mode = await service_config.get("auth_mode") or "optional"

    harmony_public_url = await service_config.get("harmony_public_url") or ""
    redis_client = await get_async_redis()
    logger.info(f"JWT authentication initialized (auth_mode={auth_mode})")
    return jwt_private_key, jwt_public_key, auth_mode, harmony_public_url, redis_client


async def _init_admin_services(  # noqa: PLR0913, PLR0914
    pool: AsyncConnectionPool,
    secret_service: SecretValueService,
    model_settings_store: ModelSettingsStore,
    settings: Settings,
    llm_service: LLMService,
    es_service: ElasticsearchService,
    qdrant_service: QdrantService | None,
) -> tuple:
    admin_settings.config_storage_path.mkdir(parents=True, exist_ok=True)
    admin_settings.job_log_path.mkdir(parents=True, exist_ok=True)

    _config_store_singleton.initialize(admin_settings.config_storage_path)
    config_store = _config_store_singleton

    if settings.job_executor == "kubernetes":
        job_executor: JobExecutor = KubernetesJobExecutor(
            namespace=admin_settings.k8s_namespace,
            job_image=admin_settings.k8s_job_image,
            data_pvc_name=admin_settings.k8s_data_pvc_name,
            models_pvc_name=admin_settings.k8s_models_pvc_name,
        )
    else:
        job_executor = SubprocessJobExecutor()

        redis_client = await get_async_redis()

    job_manager = JobManager(
        pool=pool,
        executor=job_executor,
        config_store=config_store,
        redis_client=redis_client,
    )
    await job_manager.initialize(job_log_path=admin_settings.job_log_path)

    log_streamer = LogStreamer(pool=pool)

    crawl_config_service = CrawlConfigService()
    await crawl_config_service.initialize(pool)
    await crawl_config_service.import_from_filesystem(
        admin_settings.config_storage_path / "crawler",
        created_by=None,
    )

    provider_registry = ProviderRegistry()
    data_sources_service = DataSourcesService()
    await data_sources_service.initialize(pool)

    await data_sources_service.promote_crawler_configs(crawl_config_service)

    indexer_config_service = IndexerConfigService()
    await indexer_config_service.initialize(pool)
    await indexer_config_service.import_from_filesystem_if_empty(
        admin_settings.config_storage_path / "indexer"
    )

    audit_log_service = AuditLogService()
    await audit_log_service.initialize(pool)

    model_repo = ModelRegistryRepo(pool)
    model_host_repo = ModelHostRepo(pool)
    llm_api_key_repo = LLMApiKeyRepo(pool)

    model_registry_service = ModelRegistryService()
    await model_registry_service.initialize(
        pool,
        audit_log_service,
        secret_service,
        model_host_repo,
        llm_api_key_repo,
    )

    llm_service.set_model_registry(model_registry_service)

    model_host_service = ModelHostService()
    await model_host_service.initialize(pool, model_repo, audit_log_service)

    llm_api_key_service = LLMApiKeyService()
    await llm_api_key_service.initialize(
        pool, model_repo, audit_log_service, secret_service
    )

    db_url = os.environ.get("DATABASE_URL", "")
    schedule_service = ScheduleService()
    if db_url:
        await schedule_service.initialize(db_url=db_url, pool=pool)

        await schedule_service.add_nightly_job(
            "audit_log_cleanup",
            func=nightly_audit_cleanup,
            hour=2,
        )
        await schedule_service.add_nightly_job(
            "conversation_ttl_cleanup",
            func=nightly_conversation_cleanup,
            hour=3,
        )
        logger.info(
            "Scheduler leadership %s",
            "acquired" if schedule_service.is_leader else "held by another replica",
        )

    webhook_service = WebhookService()
    await webhook_service.initialize(pool, audit_log_service)
    webhook_service.set_secret_service(secret_service)

    job_manager.set_webhook_service(webhook_service)
    job_manager.set_config_services(
        crawl_config_service,
        indexer_config_service,
        model_settings_store,
    )

    crawl_blacklist_repo = CrawlBlacklistRepo(pool)
    job_logs_repo = JobLogsRepo(pool)

    export_service = ExportService(
        es_service,
        qdrant_service,
        audit_log_service,
    )
    return (
        config_store,
        job_manager,
        log_streamer,
        crawl_config_service,
        provider_registry,
        data_sources_service,
        indexer_config_service,
        audit_log_service,
        model_registry_service,
        model_host_service,
        llm_api_key_service,
        schedule_service,
        webhook_service,
        crawl_blacklist_repo,
        job_logs_repo,
        export_service,
    )


def _init_orchestrator(
    llm_service: LLMService,
    prompt_manager: PromptManager,
    search_service: SearchService,
    pipeline_config: PipelineConfig,
) -> AgenticOrchestrator:
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
    return AgenticOrchestrator(
        agents=agents,
        max_refinement_rounds=pipeline_config.agentic_max_refinement_rounds,
        max_query_variants=pipeline_config.agentic_max_query_variants,
        agentic_max_sources_returned=pipeline_config.agentic_max_sources_returned,
        agentic_search_top_k=pipeline_config.agentic_search_top_k,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> typing.AsyncGenerator[None, None]:  # noqa: PLR0914
    settings = Settings()
    configure_logging(dev_mode=settings.dev_mode)
    usage_callback = UsageCallback()
    litellm.callbacks.append(usage_callback)
    logger.info("Starting Harmony API...")

    if not settings.cors_allowed_origins:
        msg = "CORS_ALLOWED_ORIGINS must be set. Comma-separated list of allowed origins (e.g. http://localhost:3001,http://localhost:8080)."
        raise RuntimeError(msg)

    (
        pool,
        service_config_store,
        model_settings_store,
        secret_service,
        model_policy_store,
    ) = await _init_db(settings)
    token_consumer_task = start_queue_consumer(
        queue=usage_callback.get_usage_queue(),
        pool=pool,
    )
    es_service, qdrant_service = await _init_storage_services(
        service_config_store, settings
    )
    (
        llm_service,
        prompt_manager,
        document_cache,
        conversation_service,
    ) = await _init_core_services(
        service_config_store, model_policy_store, pool, settings
    )

    (
        config_store,
        job_manager,
        log_streamer,
        crawl_config_service,
        provider_registry,
        data_sources_service,
        indexer_config_service,
        audit_log_service,
        model_registry_service,
        model_host_service,
        llm_api_key_service,
        schedule_service,
        webhook_service,
        crawl_blacklist_repo,
        job_logs_repo,
        export_service,
    ) = await _init_admin_services(
        pool,
        secret_service,
        model_settings_store,
        settings,
        llm_service,
        es_service,
        qdrant_service,
    )

    (
        pipeline_config,
        keyword_backend,
        external_search_service,
        search_service,
    ) = await _init_search_service(
        service_config_store,
        model_settings_store,
        settings,
        qdrant_service,
        model_registry_service,
        secret_service,
    )
    tool_registry = _init_tool_registry(
        es_service, search_service, document_cache, service_config_store
    )
    (
        jwt_private_key,
        jwt_public_key,
        auth_mode,
        harmony_public_url,
        redis_client,
    ) = await _init_auth(service_config_store)
    orchestrator = _init_orchestrator(
        llm_service, prompt_manager, search_service, pipeline_config
    )

    app_state = AppState(
        audit_log_service=audit_log_service,
        auth_mode=auth_mode,
        config_store=config_store,
        conversation_service=conversation_service,
        crawl_blacklist_repo=crawl_blacklist_repo,
        crawl_config_service=crawl_config_service,
        data_sources_service=data_sources_service,
        db_pool=pool,
        document_cache=document_cache,
        es_service=es_service,
        export_service=export_service,
        external_search_service=external_search_service,
        harmony_public_url=harmony_public_url,
        indexer_config_service=indexer_config_service,
        job_logs_repo=job_logs_repo,
        job_manager=job_manager,
        jwt_private_key=jwt_private_key,
        jwt_public_key=jwt_public_key,
        keyword_backend=keyword_backend,
        llm_api_key_service=llm_api_key_service,
        llm_service=llm_service,
        log_streamer=log_streamer,
        model_host_service=model_host_service,
        model_policy_store=model_policy_store,
        model_registry_service=model_registry_service,
        model_settings_store=model_settings_store,
        orchestrator=orchestrator,
        pipeline_config=pipeline_config,
        prompt_manager=prompt_manager,
        provider_registry=provider_registry,
        qdrant_service=qdrant_service,
        redis_client=redis_client,
        schedule_service=schedule_service,
        search_service=search_service,
        secret_service=secret_service,
        service_config_store=service_config_store,
        settings=settings,
        token_consumer_task=token_consumer_task,
        tool_registry=tool_registry,
        usage_callback=usage_callback,
        webhook_service=webhook_service,
    )
    app.state = app_state

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


# Constructed separately from lifespan's app.state.settings — middleware runs before lifespan starts
apply_middlewares(app, Settings())

app.include_router(api_router)


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


def run() -> None:
    settings = Settings()
    uvicorn.run(
        "harmony.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )


if __name__ == "__main__":
    run()
