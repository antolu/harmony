from __future__ import annotations

from fastapi import Request

from harmony.api.agents import AgenticOrchestrator
from harmony.api.services import (
    ConversationService,
    DocumentCache,
    ElasticsearchService,
    LLMService,
    PipelineConfig,
    PromptManager,
    SearchService,
)
from harmony.api.services.admin import (
    ConfigStore,
    JobManager,
    LogStreamer,
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
