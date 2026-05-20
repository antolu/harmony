from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from harmony.api.dependencies import get_model_settings_store, get_service_config_store
from harmony.api.services.admin import ModelSettingsStore, ServiceConfigStore

router = APIRouter()


class ConfigValidationRequest(BaseModel):
    elasticsearch_url: str | None = None
    redis_url: str | None = None
    ollama_host: str | None = None


class SetupRequest(BaseModel):
    elasticsearch_url: str
    redis_url: str
    ollama_host: str | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    reranker_provider: str | None = None
    reranker_model: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None


class OllamaHostResponse(BaseModel):
    value: str
    from_env: bool


class SetupDefaults(BaseModel):
    embedding_model: str
    reranker_model: str
    llm_model: str


class ValidationResult(BaseModel):
    ok: bool
    message: str


class ValidationResponse(BaseModel):
    elasticsearch: ValidationResult | None = None
    redis: ValidationResult | None = None
    ollama: ValidationResult | None = None


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
    if config.ollama_host:
        ok, message = await service_config.validate_ollama(config.ollama_host)
        result.ollama = ValidationResult(ok=ok, message=message)
    return result


@router.get("/ollama-host", response_model=OllamaHostResponse)
async def get_ollama_host(
    service_config: ServiceConfigStore = Depends(get_service_config_store),
) -> OllamaHostResponse:
    from_env = service_config.is_from_env("ollama_host")
    value = await service_config.get("ollama_host")
    return OllamaHostResponse(value=value, from_env=from_env)


@router.get("/defaults", response_model=SetupDefaults)
async def get_setup_defaults(
    service_config: ServiceConfigStore = Depends(get_service_config_store),
) -> SetupDefaults:
    ollama_host = await service_config.get("ollama_host")
    if ollama_host:
        return SetupDefaults(
            embedding_model="ollama/qwen3-embedding:0.6b",
            reranker_model="ollama/bge-reranker-v2-m3",
            llm_model="ollama_chat/llama3",
        )
    return SetupDefaults(
        embedding_model="gemini/text-embedding-004",
        reranker_model="",
        llm_model="gemini/gemini-2.0-flash",
    )


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
    await service_config.set("ollama_host", config.ollama_host or "", validated=True)

    if config.embedding_provider is not None:
        await model_settings.save_embedding_provider(config.embedding_provider)  # type: ignore[arg-type]
    if config.embedding_model is not None:
        await model_settings.save_embedding_model(config.embedding_model)
    if config.reranker_provider is not None:
        await model_settings.save_reranker_provider(config.reranker_provider)  # type: ignore[arg-type]
    if config.reranker_model is not None:
        await model_settings.save_reranker_model(config.reranker_model)
    if config.llm_provider is not None:
        await model_settings.save_llm_provider(config.llm_provider)  # type: ignore[arg-type]
    if config.llm_model is not None:
        await model_settings.save_llm_model(config.llm_model)

    return {"status": "success", "message": "Setup completed successfully"}
