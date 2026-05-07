from __future__ import annotations

import httpx
import litellm
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from harmony.api.config import settings
from harmony.api.services.admin.model_settings import model_settings_store

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
async def get_model_settings() -> dict[str, str]:
    return await model_settings_store.get_all()


@router.patch("")
async def update_model_settings(update: ModelSettingsUpdate) -> dict[str, str]:
    data = update.model_dump(exclude_none=True)

    for key, value in data.items():
        if key.endswith("_model"):
            provider_key = key.replace("_model", "_provider")
            provider = data.get(provider_key) or await model_settings_store.get(
                provider_key
            )
            await _validate_model(value, provider, key.replace("_model", ""))

        if key == "embedding_model":
            current = await model_settings_store.get("embedding_model")
            if value != current:
                await model_settings_store.set(
                    "embedding_model_changed_since_last_embed", "true"
                )

        await model_settings_store.set(key, value)

    return await model_settings_store.get_all()


@router.post("/validate")
async def validate_model_endpoint(body: ValidateRequest) -> dict[str, bool | str]:
    try:
        await _validate_model(body.model, body.provider, body.model_type)
    except HTTPException as e:
        return {"valid": False, "error": e.detail}
    else:
        return {"valid": True}


async def _validate_model(model: str, provider: str, model_type: str) -> None:
    if provider == "ollama":
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(f"{settings.ollama_host}/api/tags")
                tags = resp.json()
                pulled = {m["name"] for m in tags.get("models", [])}
                bare = model.removeprefix("ollama/")
                if bare not in pulled:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Model {model!r} not pulled in Ollama",
                    )
            except httpx.HTTPError as e:
                raise HTTPException(
                    status_code=502, detail=f"Ollama unreachable: {e}"
                ) from e
    else:
        valid = set(litellm.get_valid_models(check_provider_endpoint=True))
        if model not in valid:
            raise HTTPException(
                status_code=400,
                detail=f"Model {model!r} not recognised by litellm",
            )
