from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from harmony.api.agents import AgenticOrchestrator
from harmony.api.authz import AuthorizationContext
from harmony.api.models.user import AnonymousIdentity, UserIdentity
from harmony.api.services import (
    ConversationService,
    DocumentCache,
    ElasticsearchService,
    ExternalSearchService,
    LLMService,
    PipelineConfig,
    PromptManager,
    SearchService,
)
from harmony.api.services.admin import (
    ConfigStore,
    JobManager,
    LogStreamer,
    ModelPolicyStore,
    ModelSettingsStore,
    ServiceConfigStore,
)
from harmony.api.tools import ToolRegistry


def get_search_service(request: Request) -> SearchService:
    return request.app.state.search_service


def get_es_service(request: Request) -> ElasticsearchService:
    return request.app.state.es_service


def get_llm_service(request: Request) -> LLMService:
    return request.app.state.llm_service


def get_document_cache(request: Request) -> DocumentCache:
    return request.app.state.document_cache


def get_conversation_service(request: Request) -> ConversationService:
    return request.app.state.conversation_service


def get_tool_registry(request: Request) -> ToolRegistry:
    return request.app.state.tool_registry


def get_prompt_manager(request: Request) -> PromptManager:
    return request.app.state.prompt_manager


def get_orchestrator(request: Request) -> AgenticOrchestrator:
    return request.app.state.orchestrator


def get_pipeline_config(request: Request) -> PipelineConfig:
    return request.app.state.pipeline_config


def get_config_store(request: Request) -> ConfigStore:
    return request.app.state.config_store


def get_job_manager(request: Request) -> JobManager:
    return request.app.state.job_manager


def get_log_streamer(request: Request) -> LogStreamer:
    return request.app.state.log_streamer


def get_model_settings_store(request: Request) -> ModelSettingsStore:
    return request.app.state.model_settings_store


def get_service_config_store(request: Request) -> ServiceConfigStore:
    return request.app.state.service_config_store


def get_current_user(request: Request) -> UserIdentity | AnonymousIdentity:
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Authentication required")
    return request.state.user


def get_current_user_or_anonymous(request: Request) -> UserIdentity | AnonymousIdentity:
    if hasattr(request.state, "user"):
        return request.state.user
    return AnonymousIdentity()


def get_model_policy_store(request: Request) -> ModelPolicyStore:
    return request.app.state.model_policy_store


def get_external_search_service(request: Request) -> ExternalSearchService | None:
    return getattr(request.app.state, "external_search_service", None)


def get_secret_service(request: Request) -> object:
    return request.app.state.secret_service


def get_authz_context(
    request: Request,
    user: UserIdentity | AnonymousIdentity = Depends(get_current_user_or_anonymous),
) -> AuthorizationContext:
    trace_id = getattr(request.state, "trace_id", "")
    auth_mode = getattr(request.app.state, "auth_mode", "optional")
    return AuthorizationContext.from_user_identity(
        user,
        trace_id=trace_id,
        auth_mode=auth_mode,
    )
