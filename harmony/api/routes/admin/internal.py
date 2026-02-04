from __future__ import annotations

import json
import typing

from fastapi import APIRouter, Body
from pydantic import BaseModel

from harmony.db.connection import get_async_pool
from harmony.db.redis_client import get_async_redis
from harmony.db.repositories import AuthSessionsRepo, SafetyListsRepo

router = APIRouter()

_STATS_KEY_PREFIX = "crawl-stats-latest:"
_STATS_CHANNEL_PREFIX = "crawl-stats:"
_STATS_TTL_SECONDS = 604800  # 7 days

_SAFETY_PENDING_CHANNEL_PREFIX = "safety-pending:"


class SafetyListPayload(BaseModel):
    pattern: str
    list_type: str


class SafetyPendingPayload(BaseModel):
    url: str
    reason: str
    pattern: str


class SafetyDecisionPayload(BaseModel):
    pattern: str
    decision: str


class SafetyListsResponse(BaseModel):
    allow: list[str]
    deny: list[str]


# ---------------------------------------------------------------------------
# Safety lists
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Auth sessions
# ---------------------------------------------------------------------------


@router.get("/auth-sessions")
async def get_auth_sessions() -> list[dict[str, typing.Any]]:
    pool = await get_async_pool()
    rows = await AuthSessionsRepo(pool).load_all()
    serialized: list[dict[str, typing.Any]] = []
    for row in rows:
        entry = dict(row)
        if entry.get("created_at"):
            entry["created_at"] = entry["created_at"].isoformat()
        if entry.get("expires_at"):
            entry["expires_at"] = entry["expires_at"].isoformat()
        serialized.append(entry)
    return serialized


@router.post("/auth-sessions", status_code=201)
async def upsert_auth_session(
    session: typing.Annotated[dict[str, typing.Any], Body()],
) -> dict[str, str]:
    pool = await get_async_pool()
    subdomain = session.get("subdomain", "")
    await AuthSessionsRepo(pool).upsert(subdomain, session)
    return {"status": "ok"}


@router.delete("/auth-sessions/{subdomain}")
async def delete_auth_session(subdomain: str) -> dict[str, str]:
    pool = await get_async_pool()
    await AuthSessionsRepo(pool).delete(subdomain)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Stats (crawler → Redis)
# ---------------------------------------------------------------------------


@router.post("/stats/{job_id}", status_code=201)
async def publish_stats(job_id: str, payload: dict[str, typing.Any]) -> dict[str, str]:
    redis = await get_async_redis()
    channel = f"{_STATS_CHANNEL_PREFIX}{job_id}"
    key = f"{_STATS_KEY_PREFIX}{job_id}"
    message = json.dumps(payload)

    await redis.publish(channel, message)

    str_payload = {str(k): str(v) for k, v in payload.items()}
    await redis.hset(key, mapping=str_payload)
    await redis.expire(key, _STATS_TTL_SECONDS)

    await redis.aclose()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Safety pending / decision (crawler ↔ frontend)
# ---------------------------------------------------------------------------


@router.post("/safety-pending/{job_id}", status_code=201)
async def publish_safety_pending(
    job_id: str, payload: SafetyPendingPayload
) -> dict[str, str]:
    redis = await get_async_redis()
    channel = f"{_SAFETY_PENDING_CHANNEL_PREFIX}{job_id}"
    message = json.dumps({
        "url": payload.url,
        "reason": payload.reason,
        "pattern": payload.pattern,
    })
    await redis.publish(channel, message)
    await redis.aclose()
    return {"status": "ok"}


@router.post("/safety-decision/{job_id}", status_code=201)
async def publish_safety_decision(
    job_id: str, payload: SafetyDecisionPayload
) -> dict[str, str]:
    if payload.decision in {"always", "never"}:
        pool = await get_async_pool()
        list_type = "allow" if payload.decision == "always" else "deny"
        await SafetyListsRepo(pool).add_pattern(payload.pattern, list_type)
    return {"status": "ok"}
