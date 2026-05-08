from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from harmony.db.connection import get_async_pool
from harmony.db.repositories import SafetyListsRepo

router = APIRouter()


class SafetyListPayload(BaseModel):
    pattern: str
    list_type: str


class SafetyListsResponse(BaseModel):
    allow: list[str]
    deny: list[str]


@router.get("/safety-lists", response_model=SafetyListsResponse)
async def get_safety_lists() -> SafetyListsResponse:
    pool = await get_async_pool()
    allow, deny = await SafetyListsRepo(pool).load_all()
    return SafetyListsResponse(allow=allow, deny=deny)


@router.post("/safety-lists", status_code=201)
async def add_safety_pattern(payload: SafetyListPayload) -> dict[str, str]:
    pool = await get_async_pool()
    await SafetyListsRepo(pool).add_pattern(payload.pattern, payload.list_type)
    return {"status": "ok"}


@router.delete("/safety-lists")
async def remove_safety_pattern(pattern: str) -> dict[str, str]:
    pool = await get_async_pool()
    await SafetyListsRepo(pool).remove_pattern(pattern)
    return {"status": "ok"}
