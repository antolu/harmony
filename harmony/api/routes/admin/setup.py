from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from harmony.api.services.admin.service_config import service_config_store

router = APIRouter()


class ConfigValidationRequest(BaseModel):
    elasticsearch_url: str | None = None
    redis_url: str | None = None


class SetupRequest(BaseModel):
    elasticsearch_url: str
    redis_url: str


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
async def get_setup_status() -> SetupStatusResponse:
    """Check if initial setup is complete."""
    is_configured = await service_config_store.is_configured()

    missing_configs = []
    if not is_configured:
        # Check which configs are missing
        for key in ["elasticsearch_url", "redis_url"]:
            value = await service_config_store.get(key)
            if not value or value == service_config_store.DEFAULTS.get(key):
                missing_configs.append(key)

    return SetupStatusResponse(
        is_configured=is_configured,
        missing_configs=missing_configs,
    )


@router.post("/validate", response_model=ValidationResponse)
async def validate_config(config: ConfigValidationRequest) -> ValidationResponse:
    """Validate Elasticsearch and/or Redis connection."""
    result = ValidationResponse()

    if config.elasticsearch_url:
        ok, message = await service_config_store.validate_elasticsearch(
            config.elasticsearch_url
        )
        result.elasticsearch = ValidationResult(ok=ok, message=message)

    if config.redis_url:
        ok, message = await service_config_store.validate_redis(config.redis_url)
        result.redis = ValidationResult(ok=ok, message=message)

    return result


@router.post("/complete")
async def complete_setup(config: SetupRequest) -> dict[str, str]:
    """Complete initial setup by validating and saving both ES and Redis configs."""
    # Validate both services
    es_ok, es_message = await service_config_store.validate_elasticsearch(
        config.elasticsearch_url
    )
    redis_ok, redis_message = await service_config_store.validate_redis(
        config.redis_url
    )

    if not es_ok:
        raise HTTPException(
            status_code=400,
            detail=f"Elasticsearch validation failed: {es_message}",
        )

    if not redis_ok:
        raise HTTPException(
            status_code=400,
            detail=f"Redis validation failed: {redis_message}",
        )

    # Save both configs atomically
    await service_config_store.set(
        "elasticsearch_url", config.elasticsearch_url, validated=True
    )
    await service_config_store.set("redis_url", config.redis_url, validated=True)

    return {"status": "success", "message": "Setup completed successfully"}
