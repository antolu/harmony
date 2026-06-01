from __future__ import annotations

import json
import typing

import psycopg_pool
import yaml

from harmony.config.indexer import IndexerConfig
from harmony.db.repositories import IndexerConfigRepo


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
        return typing.cast(dict[str, typing.Any], config_json)

    async def save(
        self,
        config_data: dict[str, typing.Any],
        updated_by: str | None,
    ) -> dict[str, typing.Any]:
        IndexerConfig.model_validate(config_data)
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
    ) -> dict[str, typing.Any]:
        data = yaml.safe_load(yaml_content)
        if not isinstance(data, dict):
            msg = "YAML must contain a mapping"
            raise TypeError(msg)
        IndexerConfig.model_validate(data)
        return await self._r.upsert(data, updated_by)
