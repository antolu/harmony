# ruff: noqa
from __future__ import annotations

from harmony._mod_replace import replace_modname
from harmony.services.admin._audit_log import AuditLogService
from harmony.services.admin._config_store import ConfigStore, config_store
from harmony.services.admin._crawl_config import CrawlConfigService
from harmony.services.admin._data_sources import DataSourcesService
from harmony.services.admin._indexer_config import IndexerConfigService
from harmony.services.admin._job_manager import JobManager
from harmony.services.admin._llm_api_keys import LLMApiKeyService
from harmony.services.admin._log_streamer import LogStreamer
from harmony.services.admin._model_hosts import DeleteResult, ModelHostService
from harmony.services.admin._model_policy import ModelPolicyStore
from harmony.services.admin._model_registry import ModelRegistryService
from harmony.services.admin._model_settings import (
    ModelSettings,
    ModelSettingsStore,
    Provider,
)
from harmony.services.admin._scheduler import (
    SCHEDULER_LEADER_LOCK_KEY,
    ScheduleService,
)
from harmony.services.admin._service_config import (
    ConfigProvider,
    ServiceConfigStore,
)
from harmony.services.admin._webhook_service import WebhookService

replace_modname(AuditLogService, __name__)
replace_modname(ConfigProvider, __name__)
replace_modname(ConfigStore, __name__)
replace_modname(CrawlConfigService, __name__)
replace_modname(DataSourcesService, __name__)
replace_modname(DeleteResult, __name__)
replace_modname(IndexerConfigService, __name__)
replace_modname(JobManager, __name__)
replace_modname(LLMApiKeyService, __name__)
replace_modname(LogStreamer, __name__)
replace_modname(ModelHostService, __name__)
replace_modname(ModelPolicyStore, __name__)
replace_modname(ModelRegistryService, __name__)
replace_modname(ModelSettings, __name__)
replace_modname(ModelSettingsStore, __name__)
replace_modname(Provider, __name__)
replace_modname(ScheduleService, __name__)
replace_modname(ServiceConfigStore, __name__)
replace_modname(WebhookService, __name__)

__all__ = [
    "SCHEDULER_LEADER_LOCK_KEY",
    "AuditLogService",
    "ConfigProvider",
    "ConfigStore",
    "CrawlConfigService",
    "DataSourcesService",
    "DeleteResult",
    "IndexerConfigService",
    "JobManager",
    "LLMApiKeyService",
    "LogStreamer",
    "ModelHostService",
    "ModelPolicyStore",
    "ModelRegistryService",
    "ModelSettings",
    "ModelSettingsStore",
    "Provider",
    "ScheduleService",
    "ServiceConfigStore",
    "WebhookService",
    "config_store",
]
