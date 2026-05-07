from __future__ import annotations

import typing

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from harmony.api.config import settings

router = APIRouter()


@router.get("")
async def list_ollama_models() -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{settings.ollama_host}/api/tags")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=502, detail=f"Ollama unreachable: {e}"
            ) from e


class PullRequest(BaseModel):
    name: str


@router.post("/pull")
async def pull_ollama_model(body: PullRequest) -> StreamingResponse:
    async def _stream() -> typing.AsyncGenerator[str, None]:
        async with (
            httpx.AsyncClient(timeout=None) as client,
            client.stream(
                "POST",
                f"{settings.ollama_host}/api/pull",
                json={"name": body.name, "stream": True},
            ) as resp,
        ):
            async for line in resp.aiter_lines():
                if line:
                    yield f"data: {line}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.delete("/{name:path}")
async def delete_ollama_model(name: str) -> dict[str, bool]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.request(
                "DELETE",
                f"{settings.ollama_host}/api/delete",
                json={"name": name},
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Ollama error: {e}") from e
    return {"deleted": True}
