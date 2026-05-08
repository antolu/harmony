from __future__ import annotations

import typing

from fastapi import APIRouter, Body

from harmony.db.connection import get_async_pool
from harmony.db.repositories import AuthSessionsRepo

router = APIRouter()


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
