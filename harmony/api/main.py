from __future__ import annotations

import typing
from contextlib import asynccontextmanager, suppress

import litellm
import structlog
import uvicorn

from harmony.db.connection import close_async_pool
from harmony.observability import UsageCallback, configure_logging, start_queue_consumer

from ._bootstrap import (
    init_admin_services,
    init_auth,
    init_core_services,
    init_db,
    init_orchestrator,
    init_search_service,
    init_storage_services,
    init_tool_registry,
)
from ._config import Settings
from ._middleware import apply_middlewares
from ._state import AppState, HarmonyApp
from .routes import router as api_router

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: HarmonyApp) -> typing.AsyncGenerator[None, None]:
    settings = Settings()
    configure_logging(dev_mode=settings.dev_mode)
    usage_callback = UsageCallback()
    litellm.callbacks.append(usage_callback)
    logger.info("Starting Harmony API...")

    if not settings.cors_allowed_origins:
        msg = "CORS_ALLOWED_ORIGINS must be set. Comma-separated list of allowed origins (e.g. http://localhost:3001,http://localhost:8080)."
        raise RuntimeError(msg)

    db = await init_db(settings)
    token_consumer_task = start_queue_consumer(
        queue=usage_callback.get_usage_queue(),
        pool=db.pool,
    )
    storage = await init_storage_services(db.service_config, settings)
    core = await init_core_services(
        db.service_config, db.model_policy_store, db.pool, settings
    )
    admin = await init_admin_services(
        db.pool,
        db.secret_service,
        db.model_settings_store,
        settings,
        core.llm_service,
        storage.es_service,
        storage.qdrant_service,
    )
    search = await init_search_service(
        db.service_config,
        db.model_settings_store,
        settings,
        storage.qdrant_service,
        admin.model_registry_service,
        db.secret_service,
    )
    tool_registry = init_tool_registry(
        storage.es_service,
        search.search_service,
        core.document_cache,
        db.service_config,
    )
    auth = await init_auth(db.service_config)
    orchestrator = init_orchestrator(
        core.llm_service,
        core.prompt_manager,
        search.search_service,
        search.pipeline_config,
    )

    app_state = AppState(
        audit_log_service=admin.audit_log_service,
        auth_mode=auth.auth_mode,
        config_store=admin.config_store,
        conversation_service=core.conversation_service,
        crawl_blacklist_repo=admin.crawl_blacklist_repo,
        crawl_config_service=admin.crawl_config_service,
        data_sources_service=admin.data_sources_service,
        db_pool=db.pool,
        document_cache=core.document_cache,
        es_service=storage.es_service,
        export_service=admin.export_service,
        external_search_service=search.external_search_service,
        harmony_public_url=auth.harmony_public_url,
        indexer_config_service=admin.indexer_config_service,
        job_logs_repo=admin.job_logs_repo,
        job_manager=admin.job_manager,
        jwt_private_key=auth.jwt_private_key,
        jwt_public_key=auth.jwt_public_key,
        keyword_backend=search.keyword_backend,
        llm_api_key_service=admin.llm_api_key_service,
        llm_service=core.llm_service,
        log_streamer=admin.log_streamer,
        model_host_service=admin.model_host_service,
        model_policy_store=db.model_policy_store,
        model_registry_service=admin.model_registry_service,
        model_settings_store=db.model_settings_store,
        orchestrator=orchestrator,
        pipeline_config=search.pipeline_config,
        prompt_manager=core.prompt_manager,
        provider_registry=admin.provider_registry,
        qdrant_service=storage.qdrant_service,
        redis_client=auth.redis_client,
        schedule_service=admin.schedule_service,
        search_service=search.search_service,
        secret_service=db.secret_service,
        service_config_store=db.service_config,
        settings=settings,
        token_consumer_task=token_consumer_task,
        tool_registry=tool_registry,
        usage_callback=usage_callback,
        webhook_service=admin.webhook_service,
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


app = HarmonyApp(
    title="Harmony API",
    description="LLM-powered information retrieval system",
    version="0.1.0",
    lifespan=lifespan,
)


# Constructed separately from lifespan's app.state.settings — middleware runs before lifespan starts
apply_middlewares(app, Settings())

app.include_router(api_router)


@app.get("/")
def root() -> dict[str, str | dict[str, str]]:
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
def api_root() -> dict[str, str | dict[str, str]]:
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
