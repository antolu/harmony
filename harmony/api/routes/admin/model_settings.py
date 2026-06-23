from __future__ import annotations

import typing

import pydantic
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from harmony.api.dependencies import require_role
from harmony.api.models.registry import ModelRegistryRow, ModelType
from harmony.api.models.user import AnonymousIdentity, UserIdentity
from harmony.api.services.admin._model_registry import (
    ConnectivityResult,
    ManifestResult,
)
from harmony.db.repositories import ModelCreateData

router = APIRouter()


class CreateModelBody(BaseModel):
    name: str
    provider: str
    model_id: str
    model_type: ModelType
    api_key_id: str | None = None
    cost_per_token: float | None = None
    enabled: bool = True
    model_host_id: str | None = None
    new_api_key_value: str | None = None
    new_api_key_name: str | None = None


_CLEAR_API_KEY = "__clear__"


class UpdateModelBody(BaseModel):
    name: str | None = None
    provider: str | None = None
    model_id: str | None = None
    model_type: ModelType | None = None
    api_key_id: str | None = None
    cost_per_token: float | None = None
    enabled: bool | None = None
    model_host_id: str | None = None
    new_api_key_value: str | None = None
    new_api_key_name: str | None = None


class UpdateGroupsBody(BaseModel):
    groups: list[str]


class ValidateModelBody(BaseModel):
    provider: str
    model: str
    model_type: ModelType
    host_id: str | None = None
    api_key_id: str | None = None


@router.get("")
async def list_models(
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> list[ModelRegistryRow]:
    return await request.app.state.model_registry_service.list_all()


@router.post("")
async def create_model(
    body: CreateModelBody,
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("admin")),
) -> ModelRegistryRow:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    api_key_id = body.api_key_id
    if body.new_api_key_value:
        key_row = await request.app.state.llm_api_key_service.create(
            name=body.new_api_key_name or "Unnamed key",
            value=body.new_api_key_value,
            created_by=user_id,
        )
        api_key_id = key_row.id

    try:
        result = await request.app.state.model_registry_service.create(
            data=ModelCreateData(
                name=body.name,
                provider=body.provider,
                model_id=body.model_id,
                model_type=body.model_type,
                api_key_id=api_key_id,
                cost_per_token=body.cost_per_token,
                enabled=body.enabled,
                model_host_id=body.model_host_id,
            ),
            api_key=None,
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
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("admin")),
) -> ModelRegistryRow:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    fields = {k: v for k, v in body.model_dump().items() if v is not None}

    new_api_key_value = fields.pop("new_api_key_value", None)
    new_api_key_name = fields.pop("new_api_key_name", None)

    if fields.get("api_key_id") == _CLEAR_API_KEY:
        fields["api_key_id"] = None

    if new_api_key_value:
        key_row = await request.app.state.llm_api_key_service.create(
            name=new_api_key_name or "Unnamed key",
            value=new_api_key_value,
            created_by=user_id,
        )
        fields["api_key_id"] = key_row.id

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
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("admin")),
) -> dict[str, bool]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    deleted = await request.app.state.model_registry_service.delete(
        model_pk=model_id,
        deleted_by=user_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    return {"deleted": True}


@router.post("/validate")
async def validate_model(
    body: ValidateModelBody,
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("admin")),
) -> ConnectivityResult:
    return await request.app.state.model_registry_service.validate_unsaved_model(
        provider=body.provider,
        model_id=body.model,
        model_type=body.model_type,
        host_id=body.host_id,
        api_key_id=body.api_key_id,
    )


@router.post("/{model_id}/test")
async def check_model_connectivity(
    model_id: str,
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("admin")),
) -> ConnectivityResult:
    return await request.app.state.model_registry_service.test_connectivity(model_id)


@router.get("/manifest")
async def get_model_manifest(
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> ManifestResult:
    return await request.app.state.model_registry_service.get_manifest()


@router.patch("/{model_id}/groups")
async def update_model_groups(
    model_id: str,
    body: UpdateGroupsBody,
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("admin")),
) -> dict[str, pydantic.JsonValue]:
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
    return {
        "id": model_id,
        "allowed_groups": typing.cast(list[pydantic.JsonValue], body.groups),
    }
