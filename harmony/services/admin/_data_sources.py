from __future__ import annotations

import psycopg_pool
import pydantic

from harmony.db.models import DataSourceData
from harmony.db.repositories import DataSourcesRepo
from harmony.providers import ProviderRegistry

from ._crawl_config import CrawlConfigService


class DataSourcesService:
    def __init__(self) -> None:
        self._repo: DataSourcesRepo | None = None

    async def initialize(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._repo = DataSourcesRepo(pool)

    @property
    def _r(self) -> DataSourcesRepo:
        if self._repo is None:
            msg = "DataSourcesService not initialized"
            raise RuntimeError(msg)
        return self._repo

    async def list(self) -> list[DataSourceData]:
        return await self._r.list_all()

    async def get(self, data_source_id: str) -> DataSourceData | None:
        return await self._r.get(data_source_id)

    async def create(
        self,
        data: DataSourceData,
        provider_registry: ProviderRegistry,
    ) -> DataSourceData:
        provider_cls = provider_registry.get(data.provider_type)
        if provider_cls is None:
            msg = f"Unknown provider type: {data.provider_type}"
            raise ValueError(msg)
        return await self._r.create(
            name=data.name,
            provider_type=data.provider_type,
            config_data=data.config,
            description=data.description,
            created_by=data.created_by,
        )

    async def update(
        self,
        data_source_id: str,
        config_data: dict[str, pydantic.JsonValue],
        description: str | None,
    ) -> DataSourceData | None:
        existing = await self._r.get(data_source_id)
        if existing is None:
            return None
        return await self._r.update(
            data_source_id=data_source_id,
            name=existing.name,
            config_data=config_data,
            description=description,
        )

    async def delete(self, data_source_id: str) -> bool:
        existing = await self._r.get(data_source_id)
        if existing is None:
            return False
        await self._r.delete(data_source_id)
        return True

    async def promote_crawler_configs(
        self, crawl_config_service: CrawlConfigService
    ) -> None:
        configs = await crawl_config_service.list()
        for cfg in configs:
            config_data = cfg.config_json
            await self._r.create_if_not_exists(
                name=cfg.name,
                provider_type="web-crawler",
                config_data=config_data,
            )
