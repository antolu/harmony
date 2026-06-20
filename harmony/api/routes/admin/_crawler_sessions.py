from __future__ import annotations

import typing

from fastapi import APIRouter, Body, Depends

from harmony.api.dependencies import get_auth_sessions_repo, require_role
from harmony.api.models.user import AnonymousIdentity, UserIdentity
from harmony.db.repositories import AuthSessionData, AuthSessionsRepo

router = APIRouter()


@router.get("/auth-sessions")
async def get_auth_sessions(
    repo: typing.Annotated[AuthSessionsRepo, Depends(get_auth_sessions_repo)],
    _: typing.Annotated[
        UserIdentity | AnonymousIdentity, Depends(require_role("read-only"))
    ],
) -> list[dict[str, typing.Any]]:
    rows = await repo.load_all()
    serialized: list[dict[str, typing.Any]] = []
    for row in rows:
        entry: dict[str, typing.Any] = dict(row)
        created_at = row.get("created_at")
        if created_at:
            entry["created_at"] = created_at.isoformat()
        expires_at = row.get("expires_at")
        if expires_at:
            entry["expires_at"] = expires_at.isoformat()
        serialized.append(entry)
    return serialized


@router.post("/auth-sessions", status_code=201)
async def upsert_auth_session(
    session: typing.Annotated[dict[str, typing.Any], Body()],
    repo: typing.Annotated[AuthSessionsRepo, Depends(get_auth_sessions_repo)],
    _: typing.Annotated[
        UserIdentity | AnonymousIdentity, Depends(require_role("operator"))
    ],
) -> dict[str, str]:
    subdomain = session.get("subdomain", "")
    await repo.upsert(subdomain, typing.cast(AuthSessionData, session))
    return {"status": "ok"}


@router.delete("/auth-sessions/{subdomain}")
async def delete_auth_session(
    subdomain: str,
    repo: typing.Annotated[AuthSessionsRepo, Depends(get_auth_sessions_repo)],
    _: typing.Annotated[
        UserIdentity | AnonymousIdentity, Depends(require_role("operator"))
    ],
) -> dict[str, str]:
    await repo.delete(subdomain)
    return {"status": "ok"}
