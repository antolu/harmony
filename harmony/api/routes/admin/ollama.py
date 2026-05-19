from __future__ import annotations

import typing

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from harmony.api.dependencies import get_service_config_store
from harmony.api.services.admin import ServiceConfigStore

router = APIRouter()


async def _get_ollama_host(service_config: ServiceConfigStore) -> str:
    host = await service_config.get("ollama_host")
    if not host:
        raise HTTPException(status_code=503, detail="Ollama host not configured")
    return host


_RERANKER_PATTERNS = ("rerank", "cross-encoder", "cross_encoder")


def _is_reranker(name: str) -> bool:
    lower = name.lower()
    return any(p in lower for p in _RERANKER_PATTERNS)


async def _model_type(client: httpx.AsyncClient, host: str, name: str) -> str:
    if _is_reranker(name):
        return "reranker"
    try:
        resp = await client.post(f"{host}/api/show", json={"name": name})
        resp.raise_for_status()
        info = resp.json().get("model_info", {})
        has_pooling = any("pooling_type" in k for k in info)
    except Exception:
        return "chat"
    else:
        return "embedding" if has_pooling else "chat"


@router.get("")
async def list_ollama_models(
    host: str | None = None,
    service_config: ServiceConfigStore = Depends(get_service_config_store),
) -> dict:
    resolved_host = host or await _get_ollama_host(service_config)
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{resolved_host}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = data.get("models", [])
            for model in models:
                model["model_type"] = await _model_type(
                    client, resolved_host, model["name"]
                )
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=502, detail=f"Ollama unreachable: {e}"
            ) from e
        else:
            return {"models": models}


class PullRequest(BaseModel):
    name: str


@router.post("/pull")
async def pull_ollama_model(
    body: PullRequest,
    service_config: ServiceConfigStore = Depends(get_service_config_store),
) -> StreamingResponse:
    host = await _get_ollama_host(service_config)

    async def _stream() -> typing.AsyncGenerator[str, None]:
        async with (
            httpx.AsyncClient(timeout=None) as client,
            client.stream(
                "POST",
                f"{host}/api/pull",
                json={"name": body.name, "stream": True},
            ) as resp,
        ):
            async for line in resp.aiter_lines():
                if line:
                    yield f"data: {line}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.delete("/{name:path}")
async def delete_ollama_model(
    name: str,
    service_config: ServiceConfigStore = Depends(get_service_config_store),
) -> dict[str, bool]:
    host = await _get_ollama_host(service_config)
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.request(
                "DELETE",
                f"{host}/api/delete",
                json={"name": name},
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Ollama error: {e}") from e
    return {"deleted": True}
