from __future__ import annotations

import typing

import pydantic
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from harmony.api.dependencies import require_role
from harmony.db.repositories import DataSourceData
from harmony.models import AnonymousIdentity, UserIdentity

router = APIRouter()


class DataSourceCreateRequest(BaseModel):
    name: str
    provider_type: str
    config: dict[str, pydantic.JsonValue] | None = None
    description: str | None = None


class DataSourceUpdateRequest(BaseModel):
    config: dict[str, pydantic.JsonValue] | None = None
    description: str | None = None


class DataSourceListResponse(BaseModel):
    sources: list[DataSourceData]


class ProviderTypesResponse(BaseModel):
    types: list[dict[str, pydantic.JsonValue]]


@router.get("")
async def list_data_sources(
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> DataSourceListResponse:
    sources = await request.app.state.data_sources_service.list()
    return DataSourceListResponse(sources=sources)


@router.get("/provider-types")
async def list_provider_types(
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> ProviderTypesResponse:
    return ProviderTypesResponse(types=request.app.state.provider_registry.list_types())


@router.get("/{data_source_id}")
async def get_data_source(
    data_source_id: str,
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> DataSourceData:
    source = await request.app.state.data_sources_service.get(data_source_id)
    if source is None:
        raise HTTPException(
            status_code=404, detail=f"Data source '{data_source_id}' not found"
        )
    return source


@router.post("")
async def create_data_source(
    body: DataSourceCreateRequest,
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> DataSourceData:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"

    name = body.name
    provider_type = body.provider_type
    if not name or not provider_type:
        raise HTTPException(
            status_code=422, detail="'name' and 'provider_type' are required"
        )

    config_data = body.config or {}
    description = body.description
    try:
        result = await request.app.state.data_sources_service.create(
            data=typing.cast(
                DataSourceData,
                {
                    "name": name,
                    "provider_type": provider_type,
                    "config": config_data,
                    "description": description,
                    "created_by": user_id,
                },
            ),
            provider_registry=request.app.state.provider_registry,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await request.app.state.audit_log_service.record(
        user_id=user_id,
        action="data_source_created",
        entity_type="data_source",
        entity_id=result.id,
        details={"name": name, "provider_type": provider_type},
    )
    return result


@router.put("/{data_source_id}")
async def update_data_source(
    data_source_id: str,
    body: DataSourceUpdateRequest,
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> DataSourceData:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    config_data = body.config or {}
    description = body.description
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
