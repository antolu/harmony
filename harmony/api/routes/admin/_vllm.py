from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("")
async def list_vllm_models(host: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{host}/v1/models")
            resp.raise_for_status()
            data = resp.json()
            models = [{"name": m["id"]} for m in data.get("data", [])]
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"vLLM unreachable: {e}") from e
        else:
            return {"models": models}
