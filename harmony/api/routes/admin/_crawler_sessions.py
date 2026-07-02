from __future__ import annotations

import dataclasses
import typing

import pydantic
from fastapi import APIRouter, Body, Depends

from harmony.core import SessionData
from harmony.db.repositories import AuthSessionsRepo
from harmony.models import AnonymousIdentity, UserIdentity

from ..._dependencies import get_auth_sessions_repo, require_role

router = APIRouter()


@dataclasses.dataclass
class AuthSessionResponse:
    subdomain: str = ""
    created_at: str = ""
    expires_at: str = ""
    token: str = ""


@router.get("/auth-sessions")
async def get_auth_sessions(
    repo: typing.Annotated[AuthSessionsRepo, Depends(get_auth_sessions_repo)],
    _: typing.Annotated[
        UserIdentity | AnonymousIdentity, Depends(require_role("read-only"))
    ],
) -> list[AuthSessionResponse]:
    rows = await repo.load_all()
    serialized: list[AuthSessionResponse] = []
    for row in rows:
        entry = AuthSessionResponse(
            subdomain=row["subdomain"],
            created_at="",
            expires_at="",
            token=row.get("storage_state_file", "") or "",
        )
        created_at = row.get("created_at")
        if created_at:
            entry.created_at = created_at
        expires_at = row.get("expires_at")
        if expires_at:
            entry.expires_at = expires_at
        serialized.append(entry)
    return serialized


@router.post("/auth-sessions", status_code=201)
async def upsert_auth_session(
    session: typing.Annotated[dict[str, pydantic.JsonValue], Body()],
    repo: typing.Annotated[AuthSessionsRepo, Depends(get_auth_sessions_repo)],
    _: typing.Annotated[
        UserIdentity | AnonymousIdentity, Depends(require_role("operator"))
    ],
) -> dict[str, str]:
    subdomain = str(session.get("subdomain", ""))
    await repo.upsert(subdomain, typing.cast(SessionData, session))
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
