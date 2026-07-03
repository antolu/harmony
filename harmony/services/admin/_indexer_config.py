from __future__ import annotations

import json
from pathlib import Path

import psycopg_pool
import pydantic
import yaml

from harmony.db.models import IndexerConfigData
from harmony.db.repositories import IndexerConfigRepo
from harmony.indexer import IndexerConfigAdmin


class IndexerConfigService:
    def __init__(self) -> None:
        self._repo: IndexerConfigRepo | None = None

    async def initialize(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._repo = IndexerConfigRepo(pool)

    @property
    def _r(self) -> IndexerConfigRepo:
        if self._repo is None:
            msg = "IndexerConfigService not initialized"
            raise RuntimeError(msg)
        return self._repo

    async def get(self) -> dict[str, pydantic.JsonValue]:
        row = await self._r.get()
        if row is None:
            config = IndexerConfigAdmin.model_construct()
            return config.model_dump(mode="json")
        config_json = row.config_json
        if isinstance(config_json, str):
            config_json = json.loads(config_json)
        return config_json

    async def save(
        self,
        config_data: dict[str, pydantic.JsonValue],
        updated_by: str | None,
    ) -> IndexerConfigData:
        IndexerConfigAdmin.model_validate(config_data)
        return await self._r.upsert(config_data, updated_by)

    async def export_yaml(self) -> str:
        config_data = await self.get()
        return yaml.dump(
            config_data, default_flow_style=False, allow_unicode=True, sort_keys=False
        )

    async def import_yaml(
        self,
        yaml_content: str,
        updated_by: str | None,
    ) -> IndexerConfigData:
        data = yaml.safe_load(yaml_content)
        if not isinstance(data, dict):
            msg = "YAML must contain a mapping"
            raise TypeError(msg)
        IndexerConfigAdmin.model_validate(data)
        return await self._r.upsert(data, updated_by)

    async def import_from_filesystem_if_empty(
        self,
        config_dir: Path,
        updated_by: str | None = None,
    ) -> bool:
        existing = await self._r.get()
        if existing is not None:
            return False
        if not config_dir.exists():
            return False
        for yaml_file in config_dir.glob("*.yaml"):
            if yaml_file.name.startswith("__"):
                continue
            try:
                content = yaml_file.read_text()
                await self.import_yaml(content, updated_by)
            except Exception:
                continue
            else:
                return True
        return False
