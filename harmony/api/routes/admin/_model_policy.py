from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from harmony.models import AnonymousIdentity, UserIdentity
from harmony.services.admin import ModelPolicyStore

from ..._dependencies import require_role

router = APIRouter()


def _get_store(request: Request) -> ModelPolicyStore:
    return request.app.state.model_policy_store


class AssignRoleRequest(BaseModel):
    harmony_role: str


@router.get("/model-policy")
async def list_model_policy(
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("admin")),
) -> list[dict]:
    store = _get_store(request)
    return await store.list_all()


@router.post("/model-policy/{model_id}/roles", status_code=201)
async def assign_model_role(
    model_id: str,
    body: AssignRoleRequest,
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("admin")),
) -> dict:
    store = _get_store(request)
    await store.assign_role(model_id, body.harmony_role)
    roles = await store.get_allowed_roles(model_id)
    return {"model_id": model_id, "allowed_roles": roles}


@router.delete("/model-policy/{model_id}/roles/{role}", status_code=200)
async def remove_model_role(
    model_id: str,
    role: str,
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("admin")),
) -> dict:
    store = _get_store(request)
    await store.remove_role(model_id, role)
    roles = await store.get_allowed_roles(model_id)
    return {"model_id": model_id, "allowed_roles": roles}
