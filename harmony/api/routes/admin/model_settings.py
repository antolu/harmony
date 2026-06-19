from __future__ import annotations

import typing

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from harmony.api.dependencies import require_role
from harmony.api.models.registry import ModelType
from harmony.api.models.user import UserIdentity

router = APIRouter()


class CreateModelBody(BaseModel):
    name: str
    provider: str
    model_id: str
    model_type: ModelType
    api_key: str | None = None
    cost_per_token: float | None = None
    enabled: bool = True
    ollama_host: str | None = None


class UpdateModelBody(BaseModel):
    name: str | None = None
    provider: str | None = None
    model_id: str | None = None
    model_type: ModelType | None = None
    api_key: str | None = None
    cost_per_token: float | None = None
    enabled: bool | None = None
    ollama_host: str | None = None


class UpdateGroupsBody(BaseModel):
    groups: list[str]


@router.get("")
async def list_models(
    request: Request,
    _: object = Depends(require_role("read-only")),
) -> list[dict[str, typing.Any]]:
    return await request.app.state.model_registry_service.list_all()


@router.post("")
async def create_model(
    body: CreateModelBody,
    request: Request,
    current_user: object = Depends(require_role("admin")),
) -> dict[str, typing.Any]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    try:
        result = await request.app.state.model_registry_service.create(
            name=body.name,
            provider=body.provider,
            model_id=body.model_id,
            model_type=body.model_type,
            api_key=body.api_key,
            cost_per_token=body.cost_per_token,
            enabled=body.enabled,
            ollama_host=body.ollama_host,
            created_by=user_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return result


@router.put("/{model_id}")
async def update_model(
    model_id: str,
    body: UpdateModelBody,
    request: Request,
    current_user: object = Depends(require_role("admin")),
) -> dict[str, typing.Any]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    result = await request.app.state.model_registry_service.update(
        model_pk=model_id,
        fields=fields,
        updated_by=user_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    return result


@router.delete("/{model_id}")
async def delete_model(
    model_id: str,
    request: Request,
    current_user: object = Depends(require_role("admin")),
) -> dict[str, bool]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    deleted = await request.app.state.model_registry_service.delete(
        model_pk=model_id,
        deleted_by=user_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    return {"deleted": True}


@router.post("/{model_id}/test")
async def check_model_connectivity(
    model_id: str,
    request: Request,
    _: object = Depends(require_role("admin")),
) -> dict[str, typing.Any]:
    return await request.app.state.model_registry_service.test_connectivity(model_id)


@router.get("/manifest")
async def get_model_manifest(
    request: Request,
    _: object = Depends(require_role("read-only")),
) -> dict[str, typing.Any]:
    return await request.app.state.model_registry_service.get_manifest()


@router.patch("/{model_id}/groups")
async def update_model_groups(
    model_id: str,
    body: UpdateGroupsBody,
    request: Request,
    current_user: object = Depends(require_role("admin")),
) -> dict[str, typing.Any]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    pool = request.app.state.db_pool
    async with pool.connection() as conn:
        await conn.set_autocommit(True)
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE model_registry SET allowed_groups = %s WHERE id = %s",
                (body.groups, model_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=404, detail=f"Model '{model_id}' not found"
                )
    await request.app.state.audit_log_service.record(
        user_id=user_id,
        action="model_groups_updated",
        entity_type="model",
        entity_id=model_id,
        details={"groups": body.groups},
    )
    return {"id": model_id, "allowed_groups": body.groups}
