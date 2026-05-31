from __future__ import annotations

import asyncio
import json

import httpx
import litellm
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from harmony.api.dependencies import (
    get_current_user,
    get_model_settings_store,
    get_service_config_store,
)
from harmony.api.models.user import AnonymousIdentity, UserIdentity
from harmony.api.services.admin import (
    ModelSettings,
    ModelSettingsStore,
    ServiceConfigStore,
)
from harmony.api.services.admin._model_settings import _db_get, _db_save

_MAX_MODEL_ID_LENGTH = 200

router = APIRouter()


def _require_admin(current_user: UserIdentity | AnonymousIdentity) -> None:
    if (
        not isinstance(current_user, UserIdentity)
        or current_user.harmony_role != "admin"
    ):
        raise HTTPException(status_code=403, detail="Admin role required")


class AvailableModelsUpdate(BaseModel):
    models: list[str] = Field(max_length=20)

    def validate_items(self) -> None:
        for item in self.models:
            if len(item) > _MAX_MODEL_ID_LENGTH:
                raise HTTPException(
                    status_code=422,
                    detail=f"Model ID too long (max {_MAX_MODEL_ID_LENGTH} chars): {item[:50]!r}",
                )


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


@router.get("/available")
async def get_available_models(
    model_settings: ModelSettingsStore = Depends(get_model_settings_store),
) -> dict[str, list[str]]:
    raw = await _db_get("available_models")
    if raw:
        models = json.loads(raw)
    else:
        default_llm = await model_settings.get_llm_model()
        models = [default_llm]
    return {"models": models}


@router.put("/available")
async def set_available_models(
    body: AvailableModelsUpdate,
    current_user: UserIdentity | AnonymousIdentity = Depends(get_current_user),
) -> dict[str, list[str]]:
    _require_admin(current_user)
    body.validate_items()
    await _db_save("available_models", json.dumps(body.models))
    return {"models": body.models}
