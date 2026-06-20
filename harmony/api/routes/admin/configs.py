from __future__ import annotations

import typing

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from harmony.api.dependencies import require_role
from harmony.api.models.user import AnonymousIdentity, UserIdentity

router = APIRouter()


@router.get("/crawler")
async def list_crawler_configs(
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> dict[str, typing.Any]:
    configs = await request.app.state.crawl_config_service.list()
    return {"configs": configs}


@router.get("/crawler/{name}")
async def get_crawler_config(
    name: str,
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> dict[str, typing.Any]:
    config = await request.app.state.crawl_config_service.get(name)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Config '{name}' not found")
    return config


@router.post("/crawler")
async def create_crawler_config(
    body: dict[str, typing.Any],
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> dict[str, typing.Any]:
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=422, detail="'name' is required")
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"

    copy_from = body.get("copy_from")
    if copy_from:
        try:
            result = await request.app.state.crawl_config_service.duplicate(
                copy_from, name, created_by=user_id
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        await request.app.state.audit_log_service.record(
            user_id=user_id,
            action="config_duplicated",
            entity_type="crawl_config",
            entity_id=copy_from,
            details={"source": copy_from, "new_name": name},
        )
        return result

    description = body.get("description")
    config_data = body.get("config", {})
    try:
        result = await request.app.state.crawl_config_service.create(
            name=name,
            config_data=config_data,
            description=description,
            created_by=user_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await request.app.state.audit_log_service.record(
        user_id=user_id,
        action="config_created",
        entity_type="crawl_config",
        entity_id=name,
        details={"name": name},
    )
    return result


@router.put("/crawler/{name}")
async def update_crawler_config(
    name: str,
    body: dict[str, typing.Any],
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> dict[str, typing.Any]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    description = body.get("description")
    config_data = body.get("config", {})
    try:
        result = await request.app.state.crawl_config_service.update(
            name=name,
            config_data=config_data,
            description=description,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if result is None:
        raise HTTPException(status_code=404, detail=f"Config '{name}' not found")
    await request.app.state.audit_log_service.record(
        user_id=user_id,
        action="config_updated",
        entity_type="crawl_config",
        entity_id=name,
        details={"name": name},
    )
    return result


@router.delete("/crawler/{name}")
async def delete_crawler_config(
    name: str,
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> dict[str, bool]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    deleted = await request.app.state.crawl_config_service.delete(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Config '{name}' not found")
    await request.app.state.audit_log_service.record(
        user_id=user_id,
        action="config_deleted",
        entity_type="crawl_config",
        entity_id=name,
        details={"name": name},
    )
    return {"deleted": True}


@router.patch("/crawler/{name}")
async def patch_crawler_config(
    name: str,
    body: dict[str, typing.Any],
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> dict[str, typing.Any]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"

    if "name" in body:
        new_name = body["name"]
        try:
            renamed = await request.app.state.crawl_config_service.rename(
                name, new_name
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if not renamed:
            raise HTTPException(status_code=404, detail=f"Config '{name}' not found")
        await request.app.state.audit_log_service.record(
            user_id=user_id,
            action="config_renamed",
            entity_type="crawl_config",
            entity_id=name,
            details={"old_name": name, "new_name": new_name},
        )
        result = await request.app.state.crawl_config_service.get(new_name)
        return result or {"name": new_name}

    if "config" in body:
        config_data = body["config"]
        description = body.get("description")
        try:
            result = await request.app.state.crawl_config_service.update(
                name=name,
                config_data=config_data,
                description=description,
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if result is None:
            raise HTTPException(status_code=404, detail=f"Config '{name}' not found")
        await request.app.state.audit_log_service.record(
            user_id=user_id,
            action="config_updated",
            entity_type="crawl_config",
            entity_id=name,
            details={"name": name},
        )
        return result

    raise HTTPException(
        status_code=422, detail="body must contain 'name' (rename) or 'config' (update)"
    )


@router.post("/crawler/{name}/rename")
async def rename_crawler_config(
    name: str,
    body: dict[str, str],
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> dict[str, typing.Any]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    new_name = body.get("new_name")
    if not new_name:
        raise HTTPException(status_code=422, detail="'new_name' is required")
    try:
        renamed = await request.app.state.crawl_config_service.rename(name, new_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not renamed:
        raise HTTPException(status_code=404, detail=f"Config '{name}' not found")
    await request.app.state.audit_log_service.record(
        user_id=user_id,
        action="config_renamed",
        entity_type="crawl_config",
        entity_id=name,
        details={"old_name": name, "new_name": new_name},
    )
    result = await request.app.state.crawl_config_service.get(new_name)
    return result or {"name": new_name}


@router.post("/crawler/{name}/duplicate")
async def duplicate_crawler_config(
    name: str,
    body: dict[str, str],
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> dict[str, typing.Any]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    new_name = body.get("new_name")
    if not new_name:
        raise HTTPException(status_code=422, detail="'new_name' is required")
    try:
        result = await request.app.state.crawl_config_service.duplicate(
            name, new_name, created_by=user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await request.app.state.audit_log_service.record(
        user_id=user_id,
        action="config_duplicated",
        entity_type="crawl_config",
        entity_id=name,
        details={"source": name, "new_name": new_name},
    )
    return result


@router.get("/crawler/{name}/export")
async def export_crawler_config(
    name: str,
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> dict[str, str]:
    yaml_content = await request.app.state.crawl_config_service.export_yaml(name)
    if yaml_content is None:
        raise HTTPException(status_code=404, detail=f"Config '{name}' not found")
    return {"name": name, "yaml_content": yaml_content}


@router.post("/crawler/import")
async def import_crawler_config(
    file: typing.Annotated[UploadFile, File(...)],
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> dict[str, typing.Any]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    content = await file.read()
    yaml_content = content.decode("utf-8")
    try:
        result = await request.app.state.crawl_config_service.import_yaml(
            yaml_content=yaml_content,
            created_by=user_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid config: {e}") from e
    await request.app.state.audit_log_service.record(
        user_id=user_id,
        action="config_imported",
        entity_type="crawl_config",
        entity_id=result.get("name"),
        details={"name": result.get("name")},
    )
    return result


@router.get("/indexer")
async def get_indexer_config(
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> dict[str, typing.Any]:
    return await request.app.state.indexer_config_service.get()


@router.put("/indexer")
async def update_indexer_config(
    body: dict[str, typing.Any],
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> dict[str, typing.Any]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    config_data = body.get("config", body)
    try:
        result = await request.app.state.indexer_config_service.save(
            config_data=config_data,
            updated_by=user_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await request.app.state.audit_log_service.record(
        user_id=user_id,
        action="indexer_config_updated",
        entity_type="indexer_config",
        entity_id=None,
        details={},
    )
    return result


@router.get("/indexer/export")
async def export_indexer_config(
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> dict[str, str]:
    yaml_content = await request.app.state.indexer_config_service.export_yaml()
    return {"yaml_content": yaml_content}


@router.post("/indexer/import")
async def import_indexer_config(
    file: typing.Annotated[UploadFile, File(...)],
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> dict[str, typing.Any]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    content = await file.read()
    yaml_content = content.decode("utf-8")
    try:
        result = await request.app.state.indexer_config_service.import_yaml(
            yaml_content=yaml_content,
            updated_by=user_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid config: {e}") from e
    await request.app.state.audit_log_service.record(
        user_id=user_id,
        action="indexer_config_updated",
        entity_type="indexer_config",
        entity_id=None,
        details={"source": "import"},
    )
    return result
