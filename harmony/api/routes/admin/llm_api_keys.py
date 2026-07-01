from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from harmony.api.dependencies import require_role
from harmony.api.models.registry import LLMApiKeyRow
from harmony.models import AnonymousIdentity, UserIdentity

router = APIRouter()


class LLMApiKeyCreateRequest(BaseModel):
    name: str
    value: str


class LLMApiKeyUpdateRequest(BaseModel):
    name: str | None = None
    value: str | None = None


@router.get("")
async def list_llm_api_keys(
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> list[LLMApiKeyRow]:
    return await request.app.state.llm_api_key_service.list_all()


@router.post("")
async def create_llm_api_key(
    body: LLMApiKeyCreateRequest,
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("admin")),
) -> LLMApiKeyRow:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    try:
        return await request.app.state.llm_api_key_service.create(
            name=body.name,
            value=body.value,
            created_by=user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put("/{key_id}")
async def update_llm_api_key(
    key_id: str,
    body: LLMApiKeyUpdateRequest,
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("admin")),
) -> LLMApiKeyRow:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    row = await request.app.state.llm_api_key_service.update(
        key_id, name=body.name, value=body.value, updated_by=user_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Key not found")
    return row


@router.delete("/{key_id}")
async def delete_llm_api_key(
    key_id: str,
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("admin")),
) -> dict[str, object]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    result = await request.app.state.llm_api_key_service.delete(
        key_id, deleted_by=user_id
    )
    return {"deleted": True, "model_count": result.model_count}
