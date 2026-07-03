import asyncio
import dataclasses
from typing import TYPE_CHECKING

import fastapi

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.rsa import (
        RSAPrivateKey,
        RSAPublicKey,
    )
    from psycopg_pool import AsyncConnectionPool
    from redis.asyncio import Redis

    from harmony.agents import AgenticOrchestrator
    from harmony.clients import ElasticsearchService, QdrantService
    from harmony.db.repositories import CrawlBlacklistRepo, JobLogsRepo
    from harmony.infrastructure.search import HarmonyKeywordBackend
    from harmony.observability import UsageCallback
    from harmony.providers import ProviderRegistry
    from harmony.services import (
        ConversationService,
        DocumentCacheProtocol,
        ExternalSearchService,
        LLMService,
        PipelineConfig,
        PromptManager,
        SearchService,
        SecretValueService,
    )
    from harmony.services.admin import (
        AuditLogService,
        ConfigStore,
        CrawlConfigService,
        DataSourcesService,
        ExportService,
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
    from harmony.tools import ToolRegistry

    from ._config import Settings


@dataclasses.dataclass
class AppState:
    audit_log_service: "AuditLogService"
    auth_mode: str
    config_store: "ConfigStore"
    conversation_service: "ConversationService"
    crawl_blacklist_repo: "CrawlBlacklistRepo"
    crawl_config_service: "CrawlConfigService"
    data_sources_service: "DataSourcesService"
    db_pool: "AsyncConnectionPool"
    document_cache: "DocumentCacheProtocol"
    es_service: "ElasticsearchService"
    export_service: "ExportService"
    external_search_service: "ExternalSearchService"
    harmony_public_url: str
    indexer_config_service: "IndexerConfigService"
    job_logs_repo: "JobLogsRepo"
    job_manager: "JobManager"
    jwt_private_key: "RSAPrivateKey"
    jwt_public_key: "RSAPublicKey"
    keyword_backend: "HarmonyKeywordBackend"
    llm_api_key_service: "LLMApiKeyService"
    llm_service: "LLMService"
    log_streamer: "LogStreamer"
    model_host_service: "ModelHostService"
    model_policy_store: "ModelPolicyStore"
    model_registry_service: "ModelRegistryService"
    model_settings_store: "ModelSettingsStore"
    orchestrator: "AgenticOrchestrator"
    pipeline_config: "PipelineConfig"
    prompt_manager: "PromptManager"
    provider_registry: "ProviderRegistry"
    redis_client: "Redis"
    schedule_service: "ScheduleService"
    search_service: "SearchService"
    secret_service: "SecretValueService"
    service_config_store: "ServiceConfigStore"
    settings: "Settings"
    tool_registry: "ToolRegistry"
    usage_callback: "UsageCallback"
    webhook_service: "WebhookService"

    # Qdrant connection can fail at startup
    qdrant_service: "QdrantService | None"

    # Task is None until _init_db runs
    token_consumer_task: "asyncio.Task | None"


class HarmonyApp(fastapi.FastAPI):
    state: AppState  # type: ignore[assignment]  # narrows Starlette's untyped State bag to our typed dataclass
