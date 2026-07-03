from __future__ import annotations

import typing

from ._audit import AuditEventRepo
from ._auth import ApiKeysRepo, AuthSessionsRepo, UsersRepo
from ._config import IndexerConfigRepo, ServiceConfigRepo
from ._data_sources import DataSourcesRepo, FilesystemStateRepo
from ._jobs import IndexerCheckpointRepo, JobLogsRepo, JobsRepo
from ._llm_api_keys import LLMApiKeyRepo
from ._model_hosts import ModelHostRepo
from ._models import ModelPolicyRepo, ModelRegistryRepo
from ._usage import MessageFeedbackRepo, SearchQueryLogRepo, TokenUsageRepo
from ._web_crawler import CrawlBlacklistRepo, CrawlConfigRepo, SafetyListsRepo
from ._webhooks import WebhookRepo

__all__ = [
    "ApiKeysRepo",
    "AuditEventRepo",
    "AuthSessionsRepo",
    "CrawlBlacklistRepo",
    "CrawlConfigRepo",
    "DataSourcesRepo",
    "FilesystemStateRepo",
    "IndexerCheckpointRepo",
    "IndexerConfigRepo",
    "JobLogsRepo",
    "JobsRepo",
    "LLMApiKeyRepo",
    "MessageFeedbackRepo",
    "ModelHostRepo",
    "ModelPolicyRepo",
    "ModelRegistryRepo",
    "SafetyListsRepo",
    "SearchQueryLogRepo",
    "ServiceConfigRepo",
    "TokenUsageRepo",
    "UsersRepo",
    "WebhookRepo",
]


def replace_modname(cls: typing.Any, modname: str) -> None:  # noqa: RUF067
    cls.__module__ = modname


for _cls in (  # noqa: RUF067
    ApiKeysRepo,
    AuditEventRepo,
    AuthSessionsRepo,
    CrawlBlacklistRepo,
    CrawlConfigRepo,
    DataSourcesRepo,
    FilesystemStateRepo,
    IndexerCheckpointRepo,
    IndexerConfigRepo,
    JobLogsRepo,
    JobsRepo,
    LLMApiKeyRepo,
    MessageFeedbackRepo,
    ModelHostRepo,
    ModelPolicyRepo,
    ModelRegistryRepo,
    SafetyListsRepo,
    SearchQueryLogRepo,
    ServiceConfigRepo,
    TokenUsageRepo,
    UsersRepo,
    WebhookRepo,
):
    replace_modname(_cls, __name__)
