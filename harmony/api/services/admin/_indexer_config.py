from __future__ import annotations

import json
import typing
from pathlib import Path

import psycopg_pool
import yaml

from harmony.config.indexer import IndexerConfig
from harmony.db.repositories import IndexerConfigRepo

_CLI_ONLY_FIELDS = {"data_dir", "source", "es_config", "verbose"}


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

    async def get(self) -> dict[str, typing.Any]:
        row = await self._r.get()
        if row is None:
            config = IndexerConfig.model_construct()
            return config.model_dump(mode="json")
        config_json = row["config_json"]
        if isinstance(config_json, str):
            config_json = json.loads(config_json)
        return {k: v for k, v in config_json.items() if k not in _CLI_ONLY_FIELDS}

    async def save(
        self,
        config_data: dict[str, typing.Any],
        updated_by: str | None,
    ) -> dict[str, typing.Any]:
        config_data = {
            k: v for k, v in config_data.items() if k not in _CLI_ONLY_FIELDS
        }
        IndexerConfig.model_validate(config_data)
        return dict(await self._r.upsert(config_data, updated_by))

    async def export_yaml(self) -> str:
        config_data = await self.get()
        return yaml.dump(
            config_data, default_flow_style=False, allow_unicode=True, sort_keys=False
        )

    async def import_yaml(
        self,
        yaml_content: str,
        updated_by: str | None,
    ) -> dict[str, typing.Any]:
        data = yaml.safe_load(yaml_content)
        if not isinstance(data, dict):
            msg = "YAML must contain a mapping"
            raise TypeError(msg)
        IndexerConfig.model_validate(data)
        return dict(await self._r.upsert(data, updated_by))

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
