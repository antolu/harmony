from __future__ import annotations

import dataclasses
from datetime import datetime
from enum import StrEnum

import pydantic


class ModelType(StrEnum):
    llm = "llm"
    embedding = "embedding"
    reranker = "reranker"
    vision = "vision"


@dataclasses.dataclass
class AuditEventData:
    id: str
    user_id: str
    user_email: str
    action: str
    entity_type: str
    entity_id: str | None
    details: dict[str, pydantic.JsonValue]
    created_at: datetime


@dataclasses.dataclass
class UserData:
    id: str
    sub: str
    email: str | None
    display_name: str | None
    harmony_role: str
    created_at: str
    last_login_at: str | None


@dataclasses.dataclass
class ApiKeyData:
    key: str
    description: str
    created_at: str
    revoked_at: str | None


@dataclasses.dataclass
class ServiceConfigData:
    key: str
    value: str
    description: str
    is_configured: bool
    validated_at: str | None
    updated_at: str | None


@dataclasses.dataclass
class IndexerConfigData:
    id: str
    config_json: dict[str, pydantic.JsonValue]
    updated_by: str | None
    updated_at: datetime


@dataclasses.dataclass
class DataSourceData:
    id: str
    name: str
    provider_type: str
    config: dict[str, pydantic.JsonValue]
    description: str | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime
    last_run_at: datetime | None
    last_run_status: str | None
    last_run_doc_count: int | None


@dataclasses.dataclass
class JobData:
    id: str
    type: str
    status: str
    config_name: str
    started_at: str | None
    finished_at: str | None
    pid: int | None
    log_file: str | None
    error: str | None
    progress_pages_crawled: int = 0
    progress_pages_pending: int = 0
    progress_requests_made: int = 0
    progress_pages_per_min: float = 0.0
    progress_current_url: str | None = None
    progress_documents_indexed: int = 0
    progress_total_documents: int = 0
    progress_current_phase: str | None = None
    progress_timestamp: datetime | None = None


@dataclasses.dataclass
class JobLogData:
    id: str
    job_id: str
    level: str
    message: str
    created_at: datetime


@dataclasses.dataclass(frozen=True)
class LLMApiKeyRow:
    id: str
    name: str
    value_encrypted: str | None
    created_at: datetime
    updated_at: datetime
    value_set: bool = False
    model_count: int = 0


@dataclasses.dataclass
class LLMApiKeyCreateData:
    name: str
    value_encrypted: str


@dataclasses.dataclass(frozen=True)
class ModelHostRow:
    id: str
    name: str
    url: str
    host_type: str
    created_at: datetime
    updated_at: datetime
    model_count: int = 0


@dataclasses.dataclass
class ModelHostCreateData:
    name: str
    url: str
    host_type: str


@dataclasses.dataclass(frozen=True)
class ModelRegistryRow:
    id: str
    name: str
    provider: str
    model_id: str
    model_type: str
    model_host_id: str | None
    api_key_id: str | None
    allowed_groups: list[str]
    cost_per_token: float | None
    enabled: bool
    created_at: datetime
    updated_at: datetime
    env_override: bool = False
    api_key_set: bool = False
    litellm_model_id: str = ""
    model_host: str | None = None
    api_key_name: str | None = None


@dataclasses.dataclass
class ModelCreateData:
    name: str
    provider: str
    model_id: str
    model_type: ModelType
    api_key_id: str | None
    cost_per_token: float | None
    enabled: bool
    model_host_id: str | None


@dataclasses.dataclass
class SearchLogData:
    user_id: str
    query: str
    language: str | None
    result_count: int | None
    latency_ms: int | None
    tokens: int | None
    mode: str | None


@dataclasses.dataclass
class CrawlConfigData:
    id: str
    name: str
    description: str | None
    config_json: dict[str, pydantic.JsonValue]
    created_by: str | None
    created_at: datetime
    updated_at: datetime


@dataclasses.dataclass
class CrawlBlacklistData:
    id: str
    pattern: str
    reason: str | None
    created_by: str
    created_at: datetime


@dataclasses.dataclass
class WebhookDeliveryData:
    webhook_id: str
    event: str
    status: str
    attempts: int
    error: str | None
    delivered_at: datetime | None


@dataclasses.dataclass(kw_only=True)
class WebhookData:
    id: str
    url: str
    events: list[str]
    enabled: bool
    created_by: str
    created_at: datetime
    secret_encrypted: str | None = None
