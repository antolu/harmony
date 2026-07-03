from __future__ import annotations

import dataclasses
import os
import typing

import structlog

from harmony.db.redis_client import get_async_redis
from harmony.db.repositories import (
    CrawlBlacklistRepo,
    JobLogsRepo,
    LLMApiKeyRepo,
    ModelHostRepo,
    ModelRegistryRepo,
)
from harmony.providers import ProviderRegistry
from harmony.services.admin import (
    AuditLogService,
    CrawlConfigService,
    DataSourcesService,
    ExportService,
    IndexerConfigService,
    JobManager,
    LLMApiKeyService,
    LogStreamer,
    ModelHostService,
    ModelRegistryService,
    ScheduleService,
    WebhookService,
    admin_settings,
)
from harmony.services.admin import (
    config_store as _config_store_singleton,
)
from harmony.services.admin.jobs import (
    JobExecutor,
    KubernetesJobExecutor,
    SubprocessJobExecutor,
)

from ._maintenance import nightly_audit_cleanup, nightly_conversation_cleanup

if typing.TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool

    from harmony.clients import ElasticsearchService, QdrantService
    from harmony.services import LLMService, SecretValueService
    from harmony.services.admin import (
        ConfigStore,
        ModelSettingsStore,
    )

    from .._config import Settings

logger = structlog.get_logger(__name__)


@dataclasses.dataclass(frozen=True)
class AdminServices:
    config_store: ConfigStore
    job_manager: JobManager
    log_streamer: LogStreamer
    crawl_config_service: CrawlConfigService
    provider_registry: ProviderRegistry
    data_sources_service: DataSourcesService
    indexer_config_service: IndexerConfigService
    audit_log_service: AuditLogService
    model_registry_service: ModelRegistryService
    model_host_service: ModelHostService
    llm_api_key_service: LLMApiKeyService
    schedule_service: ScheduleService
    webhook_service: WebhookService
    crawl_blacklist_repo: CrawlBlacklistRepo
    job_logs_repo: JobLogsRepo
    export_service: ExportService


async def init_admin_services(  # noqa: PLR0913, PLR0914
    pool: AsyncConnectionPool,
    secret_service: SecretValueService,
    model_settings_store: ModelSettingsStore,
    settings: Settings,
    llm_service: LLMService,
    es_service: ElasticsearchService,
    qdrant_service: QdrantService | None,
) -> AdminServices:
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
        admin_config=admin_settings,
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
    return AdminServices(
        config_store=config_store,
        job_manager=job_manager,
        log_streamer=log_streamer,
        crawl_config_service=crawl_config_service,
        provider_registry=provider_registry,
        data_sources_service=data_sources_service,
        indexer_config_service=indexer_config_service,
        audit_log_service=audit_log_service,
        model_registry_service=model_registry_service,
        model_host_service=model_host_service,
        llm_api_key_service=llm_api_key_service,
        schedule_service=schedule_service,
        webhook_service=webhook_service,
        crawl_blacklist_repo=crawl_blacklist_repo,
        job_logs_repo=job_logs_repo,
        export_service=export_service,
    )
