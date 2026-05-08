from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from harmony.api.dependencies import get_model_settings_store, get_service_config_store
from harmony.api.services.admin.model_settings import ModelSettingsStore
from harmony.api.services.admin.service_config import ServiceConfigStore

router = APIRouter()


class ConfigValidationRequest(BaseModel):
    elasticsearch_url: str | None = None
    redis_url: str | None = None


class SetupRequest(BaseModel):
    elasticsearch_url: str
    redis_url: str
    embedding_provider: str = "ollama"
    embedding_model: str = "ollama/qwen3-embedding:0.6b"
    reranker_provider: str = "ollama"
    reranker_model: str = "ollama/bge-reranker-v2-m3"
    llm_provider: str = "litellm"
    llm_model: str = "gemini/gemini-3-flash-preview"


class ValidationResult(BaseModel):
    ok: bool
    message: str


class ValidationResponse(BaseModel):
    elasticsearch: ValidationResult | None = None
    redis: ValidationResult | None = None


class SetupStatusResponse(BaseModel):
    is_configured: bool
    missing_configs: list[str]


@router.get("/status", response_model=SetupStatusResponse)
async def get_setup_status(
    service_config: ServiceConfigStore = Depends(get_service_config_store),
) -> SetupStatusResponse:
    is_configured = await service_config.is_configured()
    missing_configs = []
    if not is_configured:
        for key in ["elasticsearch_url", "redis_url"]:
            value = await service_config.get(key)
            if not value or value == service_config.DEFAULTS.get(key):
                missing_configs.append(key)
    return SetupStatusResponse(
        is_configured=is_configured,
        missing_configs=missing_configs,
    )


@router.post("/validate", response_model=ValidationResponse)
async def validate_config(
    config: ConfigValidationRequest,
    service_config: ServiceConfigStore = Depends(get_service_config_store),
) -> ValidationResponse:
    result = ValidationResponse()
    if config.elasticsearch_url:
        ok, message = await service_config.validate_elasticsearch(
            config.elasticsearch_url
        )
        result.elasticsearch = ValidationResult(ok=ok, message=message)
    if config.redis_url:
        ok, message = await service_config.validate_redis(config.redis_url)
        result.redis = ValidationResult(ok=ok, message=message)
    return result


@router.post("/complete")
async def complete_setup(
    config: SetupRequest,
    service_config: ServiceConfigStore = Depends(get_service_config_store),
    model_settings: ModelSettingsStore = Depends(get_model_settings_store),
) -> dict[str, str]:
    es_ok, es_message = await service_config.validate_elasticsearch(
        config.elasticsearch_url
    )
    redis_ok, redis_message = await service_config.validate_redis(config.redis_url)

    if not es_ok:
        raise HTTPException(
            status_code=400, detail=f"Elasticsearch validation failed: {es_message}"
        )
    if not redis_ok:
        raise HTTPException(
            status_code=400, detail=f"Redis validation failed: {redis_message}"
        )

    await service_config.set(
        "elasticsearch_url", config.elasticsearch_url, validated=True
    )
    await service_config.set("redis_url", config.redis_url, validated=True)

    await model_settings.save_embedding_provider(config.embedding_provider)  # type: ignore[arg-type]
    await model_settings.save_embedding_model(config.embedding_model)
    await model_settings.save_reranker_provider(config.reranker_provider)  # type: ignore[arg-type]
    await model_settings.save_reranker_model(config.reranker_model)
    await model_settings.save_llm_provider(config.llm_provider)  # type: ignore[arg-type]
    await model_settings.save_llm_model(config.llm_model)

    return {"status": "success", "message": "Setup completed successfully"}
