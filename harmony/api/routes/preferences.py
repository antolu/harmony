from __future__ import annotations

import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from harmony.api.dependencies import get_current_user
from harmony.api.models.user import AnonymousIdentity, UserIdentity

router = APIRouter()


class PreferencesUpdate(BaseModel):
    theme: Literal["light", "dark", "system"] | None = None

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, v: str | None) -> str | None:
        if v is not None and v not in {"light", "dark", "system"}:
            msg = "theme must be 'light', 'dark', or 'system'"
            raise ValueError(msg)
        return v


def _require_user(current_user: UserIdentity | AnonymousIdentity) -> UserIdentity:
    if not isinstance(current_user, UserIdentity):
        raise HTTPException(status_code=401, detail="Authentication required")
    return current_user


@router.get("/")
async def get_preferences(
    request: Request,
    current_user: Annotated[
        UserIdentity | AnonymousIdentity, Depends(get_current_user)
    ],
) -> dict:
    user = _require_user(current_user)
    pool = request.app.state.db_pool
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT preferences FROM users WHERE id = %s",
            (user.id,),
        )
        row = await cur.fetchone()
    prefs: dict = {}
    if row and row[0]:
        prefs = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    return {"theme": prefs.get("theme", "system"), "raw": prefs}


@router.patch("/")
async def update_preferences(
    body: PreferencesUpdate,
    request: Request,
    current_user: Annotated[
        UserIdentity | AnonymousIdentity, Depends(get_current_user)
    ],
) -> dict:
    user = _require_user(current_user)
    pool = request.app.state.db_pool
    updates = body.model_dump(exclude_none=True)
    if updates:
        async with pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "UPDATE users SET preferences = preferences || %s::jsonb WHERE id = %s",
                (json.dumps(updates), user.id),
            )
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT preferences FROM users WHERE id = %s",
            (user.id,),
        )
        row = await cur.fetchone()
    prefs: dict = {}
    if row and row[0]:
        prefs = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    return {"theme": prefs.get("theme", "system"), "raw": prefs}
