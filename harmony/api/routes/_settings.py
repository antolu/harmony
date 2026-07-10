from __future__ import annotations

import dataclasses

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from harmony.models import AnonymousIdentity, UserIdentity
from harmony.services import PipelineConfig
from harmony.services.admin import ConfigProvider

from .._dependencies import (
    get_pipeline_config,
    get_service_config_store,
    require_role,
)

router = APIRouter(prefix="/settings", tags=["settings"])

_OIDC_KEYS = (
    "oidc_enabled",
    "oidc_issuer_url",
    "oidc_client_id",
    "oidc_scopes",
)


class OidcSettingsUpdate(BaseModel):
    oidc_enabled: str | None = None
    oidc_issuer_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_scopes: str | None = None


@router.get("/oidc")
async def get_oidc_settings(
    service_config: ConfigProvider = Depends(get_service_config_store),
) -> dict[str, str]:
    result: dict[str, str] = {}
    for key in _OIDC_KEYS:
        result[key] = await service_config.get(key) or ""
    return result


@router.patch("/oidc")
async def update_oidc_settings(
    update: OidcSettingsUpdate,
    service_config: ConfigProvider = Depends(get_service_config_store),
    _: UserIdentity | AnonymousIdentity = Depends(require_role("admin")),
) -> dict[str, str]:
    for key, value in update.model_dump(exclude_none=True).items():
        await service_config.set(key, value)
    result: dict[str, str] = {}
    for key in _OIDC_KEYS:
        result[key] = await service_config.get(key) or ""
    return result


class PipelineConfigUpdate(BaseModel):
    keyword_candidates_n: int | None = None
    vector_top_k: int | None = None
    search_top_k: int | None = None
    vector_search_enabled: bool | None = None
    reranker_enabled: bool | None = None
    agentic_max_refinement_rounds: int | None = None
    agentic_max_query_variants: int | None = None
    agentic_search_top_k: int | None = None
    agentic_max_sources_returned: int | None = None
    ai_search_max_iterations: int | None = None
    ai_search_source_token_budget: int | None = None


@router.get("/pipeline")
async def get_pipeline_config_endpoint(
    pipeline_config: PipelineConfig = Depends(get_pipeline_config),
    service_config: ConfigProvider = Depends(get_service_config_store),
) -> dict[str, object]:
    result = dataclasses.asdict(pipeline_config)
    audit_retention_str = await service_config.get("audit_retention_days")
    conversation_ttl_str = await service_config.get("conversation_ttl_days")
    result["audit_retention_days"] = int(audit_retention_str)
    result["conversation_ttl_days"] = int(conversation_ttl_str)
    return result


class PipelineConfigRetentionUpdate(PipelineConfigUpdate):
    audit_retention_days: int | None = None
    conversation_ttl_days: int | None = None


@router.patch("/pipeline")
async def update_pipeline_config(
    update: PipelineConfigRetentionUpdate,
    request: Request,
    service_config: ConfigProvider = Depends(get_service_config_store),
    _: UserIdentity | AnonymousIdentity = Depends(require_role("admin")),
) -> dict[str, object]:
    current: PipelineConfig = request.app.state.pipeline_config
    pipeline_changes = {
        k: v
        for k, v in update.model_dump(exclude_none=True).items()
        if hasattr(current, k)
    }
    for field, value in pipeline_changes.items():
        await service_config.set(f"pipeline_{field}", str(value))
    new_config = dataclasses.replace(current, **pipeline_changes)
    request.app.state.pipeline_config = new_config
    orchestrator = request.app.state.orchestrator
    orchestrator.max_refinement_rounds = new_config.agentic_max_refinement_rounds
    orchestrator.max_query_variants = new_config.agentic_max_query_variants

    if update.audit_retention_days is not None:
        await service_config.set(
            "audit_retention_days", str(update.audit_retention_days)
        )
    if update.conversation_ttl_days is not None:
        await service_config.set(
            "conversation_ttl_days", str(update.conversation_ttl_days)
        )

    result = dataclasses.asdict(new_config)
    audit_retention_str = await service_config.get("audit_retention_days")
    conversation_ttl_str = await service_config.get("conversation_ttl_days")
    result["audit_retention_days"] = int(audit_retention_str)
    result["conversation_ttl_days"] = int(conversation_ttl_str)
    return result
