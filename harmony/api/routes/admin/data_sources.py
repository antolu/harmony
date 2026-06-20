from __future__ import annotations

import typing

from fastapi import APIRouter, Depends, HTTPException, Request

from harmony.api.dependencies import require_role
from harmony.api.models.user import AnonymousIdentity, UserIdentity

router = APIRouter()


@router.get("")
async def list_data_sources(
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> dict[str, typing.Any]:
    sources = await request.app.state.data_sources_service.list()
    return {"sources": sources}


@router.get("/provider-types")
async def list_provider_types(
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> dict[str, typing.Any]:
    return {"types": request.app.state.provider_registry.list_types()}


@router.get("/{data_source_id}")
async def get_data_source(
    data_source_id: str,
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> dict[str, typing.Any]:
    source = await request.app.state.data_sources_service.get(data_source_id)
    if source is None:
        raise HTTPException(
            status_code=404, detail=f"Data source '{data_source_id}' not found"
        )
    return source


@router.post("")
async def create_data_source(
    body: dict[str, typing.Any],
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> dict[str, typing.Any]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"

    name = body.get("name")
    provider_type = body.get("provider_type")
    if not name or not provider_type:
        raise HTTPException(
            status_code=422, detail="'name' and 'provider_type' are required"
        )

    config_data = body.get("config", {})
    description = body.get("description")
    try:
        result = await request.app.state.data_sources_service.create(
            name=name,
            provider_type=provider_type,
            config_data=config_data,
            description=description,
            created_by=user_id,
            provider_registry=request.app.state.provider_registry,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await request.app.state.audit_log_service.record(
        user_id=user_id,
        action="data_source_created",
        entity_type="data_source",
        entity_id=result["id"],
        details={"name": name, "provider_type": provider_type},
    )
    return result


@router.put("/{data_source_id}")
async def update_data_source(
    data_source_id: str,
    body: dict[str, typing.Any],
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> dict[str, typing.Any]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    config_data = body.get("config", {})
    description = body.get("description")
    result = await request.app.state.data_sources_service.update(
        data_source_id=data_source_id,
        config_data=config_data,
        description=description,
    )
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Data source '{data_source_id}' not found"
        )
    await request.app.state.audit_log_service.record(
        user_id=user_id,
        action="data_source_updated",
        entity_type="data_source",
        entity_id=data_source_id,
        details={},
    )
    return result


@router.delete("/{data_source_id}")
async def delete_data_source(
    data_source_id: str,
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> dict[str, bool]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    deleted = await request.app.state.data_sources_service.delete(data_source_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Data source '{data_source_id}' not found"
        )
    await request.app.state.audit_log_service.record(
        user_id=user_id,
        action="data_source_deleted",
        entity_type="data_source",
        entity_id=data_source_id,
        details={},
    )
    return {"deleted": True}
