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


@router.get("")
async def list_ollama_models(
    service_config: ServiceConfigStore = Depends(get_service_config_store),
) -> dict:
    host = await _get_ollama_host(service_config)
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{host}/api/tags")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=502, detail=f"Ollama unreachable: {e}"
            ) from e


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
