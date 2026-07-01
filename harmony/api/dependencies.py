from __future__ import annotations

import typing

from fastapi import Depends, HTTPException, Request

from harmony.agents import AgenticOrchestrator
from harmony.api.config import Settings
from harmony.api.services.admin import (
    ConfigStore,
    JobManager,
    LogStreamer,
    ModelPolicyStore,
    ModelSettingsStore,
    ServiceConfigStore,
)
from harmony.authz import AuthorizationContext
from harmony.clients._elasticsearch import ElasticsearchService
from harmony.db.repositories import (
    AuthSessionsRepo,
    CrawlBlacklistRepo,
    MessageFeedbackRepo,
    SafetyListsRepo,
    TokenUsageRepo,
    UsersRepo,
)
from harmony.models import AnonymousIdentity, UserIdentity
from harmony.services import (
    ConversationService,
    DocumentCache,
    ExternalSearchService,
    LLMService,
    PipelineConfig,
    PromptManager,
    SearchService,
)
from harmony.tools import ToolRegistry


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


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_safety_lists_repo(request: Request) -> SafetyListsRepo:
    return SafetyListsRepo(request.app.state.db_pool)


def get_auth_sessions_repo(request: Request) -> AuthSessionsRepo:
    return AuthSessionsRepo(request.app.state.db_pool)


def get_crawl_blacklist_repo(request: Request) -> CrawlBlacklistRepo:
    return request.app.state.crawl_blacklist_repo


def get_users_repo(request: Request) -> UsersRepo:
    return UsersRepo(request.app.state.db_pool)


def get_token_usage_repo(request: Request) -> TokenUsageRepo:
    return TokenUsageRepo(request.app.state.db_pool)


def get_message_feedback_repo(request: Request) -> MessageFeedbackRepo:
    return MessageFeedbackRepo(request.app.state.db_pool)


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


def require_role(
    required_role: str,
) -> typing.Callable[..., UserIdentity | AnonymousIdentity]:
    role_levels = {
        "service": 4,
        "admin": 3,
        "operator": 2,
        "read-only": 1,
        "read_only": 1,
    }
    required_level = role_levels.get(required_role, 0)

    def _enforce(
        current_user: UserIdentity | AnonymousIdentity = Depends(get_current_user),
    ) -> UserIdentity | AnonymousIdentity:
        user_role = (
            current_user.harmony_role if isinstance(current_user, UserIdentity) else ""
        )
        user_level = role_levels.get(user_role, 0)
        if user_level < required_level:
            raise HTTPException(
                status_code=403, detail=f"Requires {required_role} role"
            )
        return current_user

    return _enforce
