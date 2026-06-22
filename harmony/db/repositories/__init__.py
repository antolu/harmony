from __future__ import annotations

import builtins  # noqa: F401
import typing
import uuid  # noqa: F401
from datetime import datetime  # noqa: F401

import pydantic  # noqa: F401

from ._audit import AuditEventData, AuditEventRepo
from ._auth import ApiKeyData, ApiKeysRepo, AuthSessionsRepo, UserData, UsersRepo
from ._config import (
    IndexerConfigData,
    IndexerConfigRepo,
    ServiceConfigData,
    ServiceConfigRepo,
)
from ._data_sources import DataSourceData, DataSourcesRepo, FilesystemStateRepo
from ._jobs import IndexerCheckpointRepo, JobData, JobLogData, JobLogsRepo, JobsRepo
from ._llm_api_keys import LLMApiKeyCreateData, LLMApiKeyRepo
from ._models import ModelCreateData, ModelPolicyRepo, ModelRegistryRepo
from ._ollama_hosts import OllamaHostCreateData, OllamaHostRepo
from ._usage import (
    MessageFeedbackRepo,
    SearchLogData,
    SearchQueryLogRepo,
    TokenUsageRepo,
)
from ._web_crawler import (
    CrawlBlacklistData,
    CrawlBlacklistRepo,
    CrawlConfigData,
    CrawlConfigRepo,
    SafetyListsRepo,
)
from ._webhooks import WebhookData, WebhookDeliveryData, WebhookRepo

__all__ = [
    "ApiKeyData",
    "ApiKeysRepo",
    "AuditEventData",
    "AuditEventRepo",
    "AuthSessionsRepo",
    "CrawlBlacklistData",
    "CrawlBlacklistRepo",
    "CrawlConfigData",
    "CrawlConfigRepo",
    "DataSourceData",
    "DataSourcesRepo",
    "FilesystemStateRepo",
    "IndexerCheckpointRepo",
    "IndexerConfigData",
    "IndexerConfigRepo",
    "JobData",
    "JobLogData",
    "JobLogsRepo",
    "JobsRepo",
    "LLMApiKeyCreateData",
    "LLMApiKeyRepo",
    "MessageFeedbackRepo",
    "ModelCreateData",
    "ModelPolicyRepo",
    "ModelRegistryRepo",
    "OllamaHostCreateData",
    "OllamaHostRepo",
    "SafetyListsRepo",
    "SearchLogData",
    "SearchQueryLogRepo",
    "ServiceConfigData",
    "ServiceConfigRepo",
    "TokenUsageRepo",
    "UserData",
    "UsersRepo",
    "WebhookData",
    "WebhookDeliveryData",
    "WebhookRepo",
]


def replace_modname(cls: typing.Any, modname: str) -> None:  # noqa: RUF067
    cls.__module__ = modname


for _cls in (  # noqa: RUF067
    ApiKeyData,
    ApiKeysRepo,
    AuditEventData,
    AuditEventRepo,
    AuthSessionsRepo,
    CrawlBlacklistData,
    CrawlBlacklistRepo,
    CrawlConfigData,
    CrawlConfigRepo,
    DataSourceData,
    DataSourcesRepo,
    FilesystemStateRepo,
    IndexerCheckpointRepo,
    IndexerConfigData,
    IndexerConfigRepo,
    JobData,
    JobLogData,
    JobLogsRepo,
    JobsRepo,
    LLMApiKeyCreateData,
    LLMApiKeyRepo,
    MessageFeedbackRepo,
    ModelCreateData,
    ModelPolicyRepo,
    ModelRegistryRepo,
    OllamaHostCreateData,
    OllamaHostRepo,
    SafetyListsRepo,
    SearchLogData,
    SearchQueryLogRepo,
    ServiceConfigData,
    ServiceConfigRepo,
    TokenUsageRepo,
    UserData,
    UsersRepo,
    WebhookData,
    WebhookDeliveryData,
    WebhookRepo,
):
    replace_modname(_cls, __name__)
