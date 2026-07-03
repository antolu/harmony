from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from harmony.models import AnonymousIdentity, UserIdentity
from harmony.services.admin import ModelPolicyStore

from ..._dependencies import get_current_user

router = APIRouter()


def _require_admin(current_user: UserIdentity | AnonymousIdentity) -> None:
    if (
        not isinstance(current_user, UserIdentity)
        or current_user.harmony_role != "admin"
    ):
        raise HTTPException(status_code=403, detail="Admin role required")


def _get_store(request: Request) -> ModelPolicyStore:
    return request.app.state.model_policy_store


class AssignRoleRequest(BaseModel):
    harmony_role: str


@router.get("/model-policy")
async def list_model_policy(
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(get_current_user),
) -> list[dict]:
    if (
        not isinstance(current_user, UserIdentity)
        or current_user.harmony_role != "admin"
    ):
        return []
    store = _get_store(request)
    return await store.list_all()


@router.post("/model-policy/{model_id}/roles", status_code=201)
async def assign_model_role(
    model_id: str,
    body: AssignRoleRequest,
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(get_current_user),
) -> dict:
    _require_admin(current_user)
    store = _get_store(request)
    await store.assign_role(model_id, body.harmony_role)
    roles = await store.get_allowed_roles(model_id)
    return {"model_id": model_id, "allowed_roles": roles}


@router.delete("/model-policy/{model_id}/roles/{role}", status_code=200)
async def remove_model_role(
    model_id: str,
    role: str,
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(get_current_user),
) -> dict:
    _require_admin(current_user)
    store = _get_store(request)
    await store.remove_role(model_id, role)
    roles = await store.get_allowed_roles(model_id)
    return {"model_id": model_id, "allowed_roles": roles}
