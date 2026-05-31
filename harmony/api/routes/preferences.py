from __future__ import annotations

import json
import typing
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from harmony.api.dependencies import get_current_user
from harmony.api.models.user import AnonymousIdentity, UserIdentity

router = APIRouter()

PREFERENCE_DEFAULTS: dict[str, typing.Any] = {"theme": "system"}


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


def _safe_prefs(raw: dict[str, typing.Any] | None) -> dict[str, typing.Any]:
    source = raw or {}
    return {
        **PREFERENCE_DEFAULTS,
        **{k: v for k, v in source.items() if k in PREFERENCE_DEFAULTS},
    }


@router.get("/")
async def get_preferences(
    request: Request,
    current_user: Annotated[
        UserIdentity | AnonymousIdentity, Depends(get_current_user)
    ],
) -> dict[str, typing.Any]:
    user = _require_user(current_user)
    pool = request.app.state.db_pool
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT preferences FROM users WHERE id = %s",
            (user.id,),
        )
        row = await cur.fetchone()
    raw: dict[str, typing.Any] | None = None
    if row and row[0]:
        raw = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    return _safe_prefs(raw)


@router.patch("/")
async def update_preferences(
    body: PreferencesUpdate,
    request: Request,
    current_user: Annotated[
        UserIdentity | AnonymousIdentity, Depends(get_current_user)
    ],
) -> dict[str, typing.Any]:
    user = _require_user(current_user)
    pool = request.app.state.db_pool
    all_updates = body.model_dump(exclude_none=True)
    safe_updates = {k: v for k, v in all_updates.items() if k in PREFERENCE_DEFAULTS}
    if safe_updates:
        async with pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE users SET preferences = preferences || %s::jsonb "
                    "WHERE id = %s RETURNING preferences",
                    (json.dumps(safe_updates), user.id),
                )
                row = await cur.fetchone()
        raw2: dict[str, typing.Any] | None = None
        if row and row[0]:
            raw2 = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        return _safe_prefs(raw2)
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT preferences FROM users WHERE id = %s",
            (user.id,),
        )
        row = await cur.fetchone()
    raw: dict[str, typing.Any] | None = None
    if row and row[0]:
        raw = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    return _safe_prefs(raw)
