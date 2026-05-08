from __future__ import annotations

import typing

import pydantic
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from harmony.api.dependencies import get_config_store, get_service_config_store
from harmony.api.models.config import (
    ConfigEntry,
    ConfigListResponse,
    ConfigRenameRequest,
    ConfigSaveRequest,
    ConfigType,
    YamlExportResponse,
)
from harmony.api.services.admin import ConfigStore, ServiceConfigStore

router = APIRouter()


def _file_dep() -> UploadFile:
    return File(...)


@router.get("/crawler", response_model=ConfigListResponse)
async def list_crawler_configs(
    config_store: ConfigStore = Depends(get_config_store),
) -> ConfigListResponse:
    """List all saved crawler configurations."""
    configs = config_store.list_configs("crawler")
    return ConfigListResponse(configs=configs)


@router.get("/indexer", response_model=ConfigListResponse)
async def list_indexer_configs(
    config_store: ConfigStore = Depends(get_config_store),
) -> ConfigListResponse:
    """List all saved indexer configurations."""
    configs = config_store.list_configs("indexer")
    return ConfigListResponse(configs=configs)


@router.get("/crawler/{name}", response_model=dict[str, pydantic.JsonValue])
async def get_crawler_config(
    name: str,
    config_store: ConfigStore = Depends(get_config_store),
) -> dict[str, pydantic.JsonValue]:
    """Get a specific crawler configuration."""
    config = config_store.get_config("crawler", name)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Config '{name}' not found")
    return config


@router.get("/indexer/{name}", response_model=dict[str, pydantic.JsonValue])
async def get_indexer_config(
    name: str,
    config_store: ConfigStore = Depends(get_config_store),
) -> dict[str, pydantic.JsonValue]:
    """Get a specific indexer configuration."""
    config = config_store.get_config("indexer", name)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Config '{name}' not found")
    return config


@router.post("/crawler", response_model=ConfigEntry)
async def save_crawler_config(
    request: ConfigSaveRequest,
    config_store: ConfigStore = Depends(get_config_store),
) -> ConfigEntry:
    """Save a crawler configuration."""
    try:
        return config_store.save_config(
            "crawler", request.name, request.config, request.description
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/indexer", response_model=ConfigEntry)
async def save_indexer_config(
    request: ConfigSaveRequest,
    config_store: ConfigStore = Depends(get_config_store),
) -> ConfigEntry:
    """Save an indexer configuration."""
    try:
        return config_store.save_config(
            "indexer", request.name, request.config, request.description
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/crawler/{name}")
async def delete_crawler_config(
    name: str,
    config_store: ConfigStore = Depends(get_config_store),
) -> dict[str, bool]:
    """Delete a crawler configuration."""
    deleted = config_store.delete_config("crawler", name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Config '{name}' not found")
    return {"deleted": True}


@router.delete("/indexer/{name}")
async def delete_indexer_config(
    name: str,
    config_store: ConfigStore = Depends(get_config_store),
) -> dict[str, bool]:
    """Delete an indexer configuration."""
    deleted = config_store.delete_config("indexer", name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Config '{name}' not found")
    return {"deleted": True}


@router.get("/crawler/{name}/export", response_model=YamlExportResponse)
async def export_crawler_config(
    name: str,
    config_store: ConfigStore = Depends(get_config_store),
) -> YamlExportResponse:
    """Export a crawler configuration as YAML."""
    yaml_content = config_store.export_yaml("crawler", name)
    if yaml_content is None:
        raise HTTPException(status_code=404, detail=f"Config '{name}' not found")
    return YamlExportResponse(name=name, yaml_content=yaml_content)


@router.get("/indexer/{name}/export", response_model=YamlExportResponse)
async def export_indexer_config(
    name: str,
    config_store: ConfigStore = Depends(get_config_store),
) -> YamlExportResponse:
    """Export an indexer configuration as YAML."""
    yaml_content = config_store.export_yaml("indexer", name)
    if yaml_content is None:
        raise HTTPException(status_code=404, detail=f"Config '{name}' not found")
    return YamlExportResponse(name=name, yaml_content=yaml_content)


@router.get("/crawler/{name}/download")
async def download_crawler_config(
    name: str,
    config_store: ConfigStore = Depends(get_config_store),
) -> Response:
    """Download a crawler configuration as a YAML file."""
    yaml_content = config_store.export_yaml("crawler", name)
    if yaml_content is None:
        raise HTTPException(status_code=404, detail=f"Config '{name}' not found")
    return Response(
        content=yaml_content,
        media_type="application/x-yaml",
        headers={"Content-Disposition": f'attachment; filename="{name}.yaml"'},
    )


@router.get("/indexer/{name}/download")
async def download_indexer_config(
    name: str,
    config_store: ConfigStore = Depends(get_config_store),
) -> Response:
    """Download an indexer configuration as a YAML file."""
    yaml_content = config_store.export_yaml("indexer", name)
    if yaml_content is None:
        raise HTTPException(status_code=404, detail=f"Config '{name}' not found")
    return Response(
        content=yaml_content,
        media_type="application/x-yaml",
        headers={"Content-Disposition": f'attachment; filename="{name}.yaml"'},
    )


async def _import_config(
    config_type: ConfigType,
    file: UploadFile,
    name: str,
    description: str | None,
    config_store: ConfigStore,
) -> ConfigEntry:
    """Common import logic for both config types."""
    if not file.filename or not file.filename.endswith((".yaml", ".yml")):
        raise HTTPException(
            status_code=400, detail="File must be a YAML file (.yaml or .yml)"
        )

    content = await file.read()
    yaml_content = content.decode("utf-8")

    try:
        return config_store.import_yaml(config_type, name, yaml_content, description)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid config: {e}") from e


@router.post("/crawler/import", response_model=ConfigEntry)
async def import_crawler_config(
    file: typing.Annotated[UploadFile, File(...)],
    name: str = "imported",
    description: str | None = None,
    config_store: ConfigStore = Depends(get_config_store),
) -> ConfigEntry:
    """Import a crawler configuration from a YAML file."""
    return await _import_config("crawler", file, name, description, config_store)


@router.post("/indexer/import", response_model=ConfigEntry)
async def import_indexer_config(
    file: typing.Annotated[UploadFile, File(...)],
    name: str = "imported",
    description: str | None = None,
    config_store: ConfigStore = Depends(get_config_store),
) -> ConfigEntry:
    """Import an indexer configuration from a YAML file."""
    return await _import_config("indexer", file, name, description, config_store)


@router.get("/validate/elasticsearch")
async def validate_elasticsearch_connection(
    url: str,
    service_config: ServiceConfigStore = Depends(get_service_config_store),
) -> dict[str, pydantic.JsonValue]:
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    ok, message = await service_config.validate_elasticsearch(url)
    if not ok:
        raise HTTPException(status_code=503, detail=message)
    return {"valid": True, "message": message}


@router.post("/crawler/{name}/rename", response_model=ConfigEntry)
async def rename_crawler_config(
    name: str,
    request: ConfigRenameRequest,
    config_store: ConfigStore = Depends(get_config_store),
) -> ConfigEntry:
    """Rename a crawler configuration."""
    try:
        return config_store.rename_config("crawler", name, request.new_name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/indexer/{name}/rename", response_model=ConfigEntry)
async def rename_indexer_config(
    name: str,
    request: ConfigRenameRequest,
    config_store: ConfigStore = Depends(get_config_store),
) -> ConfigEntry:
    """Rename an indexer configuration."""
    try:
        return config_store.rename_config("indexer", name, request.new_name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
