from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from harmony.api.dependencies import require_role
from harmony.api.models.registry import OllamaHostRow
from harmony.api.models.user import AnonymousIdentity, UserIdentity

router = APIRouter()


class OllamaHostCreateRequest(BaseModel):
    name: str
    url: str
    host_type: str


class OllamaHostUpdateRequest(BaseModel):
    name: str | None = None
    url: str | None = None
    host_type: str | None = None


@router.get("")
async def list_ollama_hosts(
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> list[OllamaHostRow]:
    return await request.app.state.ollama_host_service.list_all()


@router.post("")
async def create_ollama_host(
    body: OllamaHostCreateRequest,
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("admin")),
) -> OllamaHostRow:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    try:
        return await request.app.state.ollama_host_service.create(
            name=body.name,
            url=body.url,
            host_type=body.host_type,
            created_by=user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put("/{host_id}")
async def update_ollama_host(
    host_id: str,
    body: OllamaHostUpdateRequest,
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("admin")),
) -> OllamaHostRow:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    fields: dict[str, object] = {}
    if body.name is not None:
        fields["name"] = body.name
    if body.url is not None:
        fields["url"] = body.url
    if body.host_type is not None:
        fields["host_type"] = body.host_type

    try:
        row = await request.app.state.ollama_host_service.update(
            host_id, fields, updated_by=user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if row is None:
        raise HTTPException(status_code=404, detail="Host not found")
    return row


@router.delete("/{host_id}")
async def delete_ollama_host(
    host_id: str,
    request: Request,
    *,
    force: bool = False,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("admin")),
) -> dict[str, object]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    result = await request.app.state.ollama_host_service.delete(
        host_id, force=force, deleted_by=user_id
    )
    if result.blocked:
        raise HTTPException(
            status_code=409,
            detail=f"{result.model_count} model(s) use this host; pass force=true to override",
        )
    return {"deleted": True, "model_count": result.model_count}
