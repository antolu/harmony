from __future__ import annotations

import json
import logging
import typing
from pathlib import Path

import psycopg_pool
import pydantic
import yaml

from harmony.db.models import CrawlConfigData
from harmony.db.repositories import CrawlConfigRepo
from harmony.providers.web_crawler import CrawlerConfig

logger = logging.getLogger(__name__)


class CrawlConfigService:
    def __init__(self) -> None:
        self._repo: CrawlConfigRepo | None = None

    async def initialize(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._repo = CrawlConfigRepo(pool)

    @property
    def _r(self) -> CrawlConfigRepo:
        if self._repo is None:
            msg = "CrawlConfigService not initialized"
            raise RuntimeError(msg)
        return self._repo

    async def list(self) -> list[CrawlConfigData]:
        return await self._r.list()

    async def get(self, name: str) -> dict[str, pydantic.JsonValue] | None:
        row = await self._r.get(name)
        if row is None:
            return None
        config_json = row.config_json
        if isinstance(config_json, str):
            config_json = json.loads(config_json)
        return typing.cast(dict[str, pydantic.JsonValue], config_json)

    async def create(
        self,
        name: str,
        config_data: dict[str, pydantic.JsonValue],
        description: str | None,
        created_by: str | None,
    ) -> CrawlConfigData:
        CrawlerConfig.model_validate(config_data)
        return await self._r.create(name, config_data, description, created_by)

    async def update(
        self,
        name: str,
        config_data: dict[str, pydantic.JsonValue],
        description: str | None,
    ) -> CrawlConfigData | None:
        CrawlerConfig.model_validate(config_data)
        return await self._r.update(name, config_data, description)

    async def rename(self, old_name: str, new_name: str) -> bool:
        return await self._r.rename(old_name, new_name)

    async def delete(self, name: str) -> bool:
        return await self._r.delete(name)

    async def duplicate(
        self,
        name: str,
        new_name: str,
        created_by: str | None,
    ) -> CrawlConfigData:
        existing = await self._r.get(name)
        if existing is None:
            msg = f"Crawl config '{name}' not found"
            raise ValueError(msg)
        config_json = existing.config_json
        if isinstance(config_json, str):
            config_json = json.loads(config_json)
        return await self._r.create(
            new_name, config_json, existing.description, created_by
        )

    async def export_yaml(self, name: str) -> str | None:
        row = await self._r.get(name)
        if row is None:
            return None
        config_json = row.config_json
        if isinstance(config_json, str):
            config_json = json.loads(config_json)
        config = CrawlerConfig.model_validate(config_json)
        return yaml.dump(
            config.model_dump(mode="json"),
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    async def import_yaml(
        self,
        yaml_content: str,
        created_by: str | None,
    ) -> CrawlConfigData:
        data = yaml.safe_load(yaml_content)
        if not isinstance(data, dict) or "name" not in data:
            msg = "YAML must contain a 'name' field"
            raise ValueError(msg)
        name = data.pop("name")
        config = CrawlerConfig.model_validate(data)
        config_json = config.model_dump(mode="json")
        existing = await self._r.get(name)
        if existing is not None:
            result = await self._r.update(name, config_json, None)
            if result is None:
                msg = f"Failed to update crawl config '{name}'"
                raise RuntimeError(msg)
            return result
        return await self._r.create(name, config_json, None, created_by)

    async def _import_yaml_file(
        self,
        yaml_file: Path,
        created_by: str | None,
    ) -> bool:
        content = yaml_file.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            return False
        name = data.pop("name", yaml_file.stem)
        if "crawler" in data and len(data) == 1:
            data = data["crawler"]
        config = CrawlerConfig.model_validate(data)
        config_json = config.model_dump(mode="json")
        existing = await self._r.get(name)
        if existing is not None:
            await self._r.update(name, config_json, None)
        else:
            await self._r.create(name, config_json, None, created_by)
        migrated_path = yaml_file.with_suffix("").with_suffix(".migrated.yaml")
        yaml_file.rename(migrated_path)
        return True

    async def import_from_filesystem(
        self,
        config_dir: Path,
        created_by: str | None = None,
    ) -> int:
        if not config_dir.exists():
            return 0
        count = 0
        for yaml_file in config_dir.glob("*.yaml"):
            if yaml_file.name.endswith(".migrated.yaml") or yaml_file.name.startswith(
                "__"
            ):
                continue
            try:
                if await self._import_yaml_file(yaml_file, created_by):
                    count += 1
            except Exception:
                logger.exception("failed to import config %s", yaml_file.name)
                continue
        return count
