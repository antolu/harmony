from __future__ import annotations

import typing

from fastapi import APIRouter, Body, Depends

from harmony.api.dependencies import get_auth_sessions_repo
from harmony.db.repositories import AuthSessionData, AuthSessionsRepo

router = APIRouter()


@router.get("/auth-sessions")
async def get_auth_sessions(
    repo: typing.Annotated[AuthSessionsRepo, Depends(get_auth_sessions_repo)],
) -> list[dict[str, typing.Any]]:
    rows = await repo.load_all()
    serialized: list[dict[str, typing.Any]] = []
    for row in rows:
        entry = dict(row)
        if entry.get("created_at"):
            entry["created_at"] = entry["created_at"].isoformat()  # type: ignore[attr-defined]
        if entry.get("expires_at"):
            entry["expires_at"] = entry["expires_at"].isoformat()  # type: ignore[attr-defined]
        serialized.append(entry)
    return serialized


@router.post("/auth-sessions", status_code=201)
async def upsert_auth_session(
    session: typing.Annotated[dict[str, typing.Any], Body()],
    repo: typing.Annotated[AuthSessionsRepo, Depends(get_auth_sessions_repo)],
) -> dict[str, str]:
    subdomain = session.get("subdomain", "")
    await repo.upsert(subdomain, typing.cast(AuthSessionData, session))
    return {"status": "ok"}


@router.delete("/auth-sessions/{subdomain}")
async def delete_auth_session(
    subdomain: str,
    repo: typing.Annotated[AuthSessionsRepo, Depends(get_auth_sessions_repo)],
) -> dict[str, str]:
    await repo.delete(subdomain)
    return {"status": "ok"}
