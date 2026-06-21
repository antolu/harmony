from __future__ import annotations

import typing

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from harmony.api.dependencies import get_crawl_blacklist_repo, get_safety_lists_repo
from harmony.db.repositories import CrawlBlacklistRepo, SafetyListsRepo

router = APIRouter()


class SafetyListPayload(BaseModel):
    pattern: str
    list_type: str


class SafetyListsResponse(BaseModel):
    allow: list[str]
    deny: list[str]


@router.get("/safety-lists", response_model=SafetyListsResponse)
async def get_safety_lists(
    repo: typing.Annotated[SafetyListsRepo, Depends(get_safety_lists_repo)],
) -> SafetyListsResponse:
    allow, deny = await repo.load_all()
    return SafetyListsResponse(allow=allow, deny=deny)


@router.post("/safety-lists", status_code=201)
async def add_safety_pattern(
    payload: SafetyListPayload,
    repo: typing.Annotated[SafetyListsRepo, Depends(get_safety_lists_repo)],
) -> dict[str, str]:
    await repo.add_pattern(payload.pattern, payload.list_type)
    return {"status": "ok"}


@router.delete("/safety-lists")
async def remove_safety_pattern(
    pattern: str,
    repo: typing.Annotated[SafetyListsRepo, Depends(get_safety_lists_repo)],
) -> dict[str, str]:
    await repo.remove_pattern(pattern)
    return {"status": "ok"}


@router.get("/blacklist")
async def get_crawl_blacklist(
    repo: typing.Annotated[CrawlBlacklistRepo, Depends(get_crawl_blacklist_repo)],
) -> dict[str, list[str]]:
    entries = await repo.list()
    return {"patterns": [entry.pattern for entry in entries]}
