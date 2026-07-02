from __future__ import annotations

import dataclasses
import json
import typing

import pydantic
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from harmony.models import AnonymousIdentity, UserIdentity

from .._dependencies import get_current_user

router = APIRouter()


@dataclasses.dataclass(frozen=True)
class UserPreferences:
    theme: str = "system"


_VALID_PREF_FIELDS = {f.name for f in dataclasses.fields(UserPreferences)}
PREFERENCE_DEFAULTS = UserPreferences()


class PreferencesUpdate(BaseModel):
    theme: typing.Literal["light", "dark", "system"] | None = None

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


def _safe_prefs(raw: dict[str, pydantic.JsonValue] | None) -> UserPreferences:
    source = raw or {}
    return UserPreferences(
        **typing.cast(
            dict[str, typing.Any],
            {k: v for k, v in source.items() if k in _VALID_PREF_FIELDS},
        )
    )


@router.get("/")
async def get_preferences(
    request: Request,
    current_user: typing.Annotated[
        UserIdentity | AnonymousIdentity, Depends(get_current_user)
    ],
) -> UserPreferences:
    user = _require_user(current_user)
    pool = request.app.state.db_pool
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT preferences FROM users WHERE id = %s",
            (user.id,),
        )
        row = await cur.fetchone()
    raw: dict[str, pydantic.JsonValue] | None = None
    if row and row[0]:
        raw = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    return _safe_prefs(raw)


@router.patch("/")
async def update_preferences(
    body: PreferencesUpdate,
    request: Request,
    current_user: typing.Annotated[
        UserIdentity | AnonymousIdentity, Depends(get_current_user)
    ],
) -> UserPreferences:
    user = _require_user(current_user)
    pool = request.app.state.db_pool
    all_updates = body.model_dump(exclude_none=True)
    safe_updates = {k: v for k, v in all_updates.items() if k in _VALID_PREF_FIELDS}
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
        raw2: dict[str, pydantic.JsonValue] | None = None
        if row and row[0]:
            raw2 = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        return _safe_prefs(raw2)
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT preferences FROM users WHERE id = %s",
            (user.id,),
        )
        row = await cur.fetchone()
    raw: dict[str, pydantic.JsonValue] | None = None
    if row and row[0]:
        raw = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    return _safe_prefs(raw)
