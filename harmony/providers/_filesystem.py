from __future__ import annotations

import typing

import pydantic

from harmony.providers._base import BaseProvider, ProviderJobSpec


class FilesystemProviderConfig(pydantic.BaseModel):
    root_path: str = pydantic.Field(
        ..., description="Root directory to index", title="Root path"
    )
    include_patterns: list[str] = pydantic.Field(
        default=["**/*"],
        description="Glob patterns for files to include",
        title="Include patterns",
    )
    exclude_patterns: list[str] = pydantic.Field(
        default=["**/.git/**", "**/node_modules/**"],
        description="Glob patterns for files to exclude",
        title="Exclude patterns",
    )
    source_name: str = pydantic.Field(
        ...,
        description="Label for this data source in search results",
        title="Source name",
    )


class FilesystemProvider(BaseProvider):
    provider_type = "filesystem"
    display_name = "Filesystem"
    description = (
        "Index files from a mounted directory (NFS, local disk, network share)"
    )

    def __init__(self, config: dict[str, typing.Any], data_source_id: str) -> None:
        self._config = FilesystemProviderConfig.model_validate(config)
        self._data_source_id = data_source_id

    @classmethod
    def config_schema(cls) -> dict[str, typing.Any]:
        return FilesystemProviderConfig.model_json_schema()

    def run(self) -> list[ProviderJobSpec]:
        return [
            ProviderJobSpec(
                entrypoint="harmony-ingest-fs",
                args=["--data-source-id", self._data_source_id],
                env={},
            )
        ]
