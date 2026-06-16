from __future__ import annotations

import typing

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from harmony.api.dependencies import require_role

router = APIRouter(prefix="/admin/users", tags=["admin"])

_VALID_ROLES = {"admin", "operator", "read-only", "anonymous"}


class UpdateRoleBody(BaseModel):
    role: str


@router.get("")
async def list_users(
    request: Request,
    _: object = Depends(require_role("admin")),
) -> dict[str, typing.Any]:
    pool = request.app.state.db_pool
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id, email, display_name, harmony_role, created_at FROM users ORDER BY email"
        )
        columns = [desc.name for desc in cur.description]
        rows = [
            typing.cast(dict[str, typing.Any], dict(zip(columns, row, strict=False)))
            for row in await cur.fetchall()
        ]
    return {"users": rows}


@router.get("/groups")
async def list_user_groups(
    _: object = Depends(require_role("read-only")),
) -> dict[str, list[str]]:
    return {"groups": sorted(_VALID_ROLES)}


@router.patch("/{user_id}")
async def update_user_role(
    user_id: str,
    body: UpdateRoleBody,
    request: Request,
    current_user: object = Depends(require_role("admin")),
) -> dict[str, typing.Any]:
    from harmony.api.models.user import UserIdentity  # noqa: PLC0415

    if body.role not in _VALID_ROLES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid role '{body.role}'. Must be one of: {', '.join(sorted(_VALID_ROLES))}",
        )
    user_id_actor = (
        current_user.id if isinstance(current_user, UserIdentity) else "system"
    )
    pool = request.app.state.db_pool
    async with pool.connection() as conn:
        await conn.set_autocommit(True)
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE users SET harmony_role = %s WHERE id = %s",
                (body.role, user_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=404, detail=f"User '{user_id}' not found"
                )
    await request.app.state.audit_log_service.record(
        user_id=user_id_actor,
        action="user_role_updated",
        entity_type="user",
        entity_id=user_id,
        details={"new_role": body.role},
    )
    return {"id": user_id, "harmony_role": body.role}
