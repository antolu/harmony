from __future__ import annotations

import json
import typing

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from harmony.db.redis_client import get_async_redis
from harmony.db.repositories import SafetyListsRepo

from ..._dependencies import get_safety_lists_repo

router = APIRouter()

_SAFETY_PENDING_CHANNEL_PREFIX = "safety-pending:"


class SafetyPendingPayload(BaseModel):
    url: str
    reason: str
    pattern: str


class SafetyDecisionPayload(BaseModel):
    pattern: str
    decision: str


@router.post("/safety-pending/{job_id}", status_code=201)
async def publish_safety_pending(
    job_id: str, payload: SafetyPendingPayload
) -> dict[str, str]:
    redis = await get_async_redis()
    try:
        channel = f"{_SAFETY_PENDING_CHANNEL_PREFIX}{job_id}"
        message = json.dumps({
            "url": payload.url,
            "reason": payload.reason,
            "pattern": payload.pattern,
        })
        await redis.publish(channel, message)
    finally:
        await redis.aclose()
    return {"status": "ok"}


@router.post("/safety-decision/{job_id}", status_code=201)
async def publish_safety_decision(
    job_id: str,
    payload: SafetyDecisionPayload,
    repo: typing.Annotated[SafetyListsRepo, Depends(get_safety_lists_repo)],
) -> dict[str, str]:
    if payload.decision in {"always", "never"}:
        list_type = "allow" if payload.decision == "always" else "deny"
        await repo.add_pattern(payload.pattern, list_type)
    return {"status": "ok"}
