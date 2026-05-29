from __future__ import annotations

import asyncio

import httpx
import litellm
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from harmony.api.dependencies import get_model_settings_store, get_service_config_store
from harmony.api.services.admin import (
    ModelSettings,
    ModelSettingsStore,
    ServiceConfigStore,
)

router = APIRouter()


class ModelSettingsUpdate(BaseModel):
    embedding_provider: str | None = None
    embedding_model: str | None = None
    reranker_provider: str | None = None
    reranker_model: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None


class ValidateRequest(BaseModel):
    model: str
    provider: str
    model_type: str


@router.get("")
async def get_model_settings(
    model_settings: ModelSettingsStore = Depends(get_model_settings_store),
) -> ModelSettings:
    return await model_settings.get_all()


@router.patch("")
async def update_model_settings(
    update: ModelSettingsUpdate,
    model_settings: ModelSettingsStore = Depends(get_model_settings_store),
    service_config: ServiceConfigStore = Depends(get_service_config_store),
) -> ModelSettings:
    if update.embedding_model is not None:
        provider = update.embedding_provider or (
            await model_settings.get_embedding_provider()
        )
        await _validate_model(
            update.embedding_model, provider, "embedding", service_config
        )

    if update.reranker_model is not None:
        provider = update.reranker_provider or (
            await model_settings.get_reranker_provider()
        )
        await _validate_model(
            update.reranker_model, provider, "reranker", service_config
        )

    if update.llm_model is not None:
        provider = update.llm_provider or (await model_settings.get_llm_provider())
        await _validate_model(update.llm_model, provider, "llm", service_config)

    if update.embedding_provider is not None:
        await model_settings.save_embedding_provider(update.embedding_provider)  # type: ignore[arg-type]
    if update.embedding_model is not None:
        current = await model_settings.get_embedding_model()
        if update.embedding_model != current:
            await model_settings.mark_embedding_changed()
        await model_settings.save_embedding_model(update.embedding_model)

    if update.reranker_provider is not None:
        await model_settings.save_reranker_provider(update.reranker_provider)  # type: ignore[arg-type]
    if update.reranker_model is not None:
        await model_settings.save_reranker_model(update.reranker_model)

    if update.llm_provider is not None:
        await model_settings.save_llm_provider(update.llm_provider)  # type: ignore[arg-type]
    if update.llm_model is not None:
        await model_settings.save_llm_model(update.llm_model)

    return await model_settings.get_all()


@router.post("/validate")
async def validate_model_endpoint(
    body: ValidateRequest,
    service_config: ServiceConfigStore = Depends(get_service_config_store),
) -> dict[str, bool | str]:
    try:
        await _validate_model(
            body.model, body.provider, body.model_type, service_config
        )
    except HTTPException as e:
        return {"valid": False, "error": e.detail}
    else:
        return {"valid": True}


async def _check_ollama_model(
    model: str, client: httpx.AsyncClient, ollama_host: str
) -> None:
    try:
        resp = await client.get(f"{ollama_host}/api/tags")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Ollama unreachable: {e}") from e
    tags = resp.json()
    pulled = {m["name"] for m in tags.get("models", [])}
    bare = model.removeprefix("ollama/")
    if bare not in pulled:
        raise HTTPException(
            status_code=400, detail=f"Model {model!r} not pulled in Ollama"
        )


async def _validate_model(
    model: str,
    provider: str,
    model_type: str,
    service_config: ServiceConfigStore,
) -> None:
    if provider == "ollama":
        ollama_host = await service_config.get("ollama_host")
        async with httpx.AsyncClient(timeout=5.0) as client:
            await _check_ollama_model(model, client, ollama_host)
    else:
        valid = await asyncio.to_thread(
            litellm.get_valid_models, check_provider_endpoint=True
        )
        if model not in set(valid):
            raise HTTPException(
                status_code=400,
                detail=f"Model {model!r} not recognised by litellm",
            )
