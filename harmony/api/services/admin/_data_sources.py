from __future__ import annotations

import typing

import psycopg_pool

from harmony.db.repositories import DataSourceData, DataSourcesRepo

if typing.TYPE_CHECKING:
    from harmony.api.services.admin._crawl_config import CrawlConfigService
    from harmony.providers import ProviderRegistry


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

    async def get(self, id: str) -> DataSourceData | None:  # noqa: A002
        return await self._r.get(id)

    async def create(  # noqa: PLR0913
        self,
        name: str,
        provider_type: str,
        config_data: dict[str, typing.Any],
        description: str | None,
        created_by: str | None,
        provider_registry: ProviderRegistry,
    ) -> DataSourceData:
        provider_cls = provider_registry.get(provider_type)
        if provider_cls is None:
            msg = f"Unknown provider type: {provider_type}"
            raise ValueError(msg)
        return await self._r.create(
            name=name,
            provider_type=provider_type,
            config_data=config_data,
            description=description,
            created_by=created_by,
        )

    async def update(
        self,
        id: str,  # noqa: A002
        config_data: dict[str, typing.Any],
        description: str | None,
    ) -> DataSourceData | None:
        existing = await self._r.get(id)
        if existing is None:
            return None
        return await self._r.update(
            id=id,
            name=existing["name"],
            config_data=config_data,
            description=description,
        )

    async def delete(self, id: str) -> bool:  # noqa: A002
        existing = await self._r.get(id)
        if existing is None:
            return False
        await self._r.delete(id)
        return True

    async def promote_crawler_configs(
        self, crawl_config_service: CrawlConfigService
    ) -> None:
        configs = await crawl_config_service.list()
        for cfg in configs:
            config_data = cfg.get("config_json", cfg.get("config", cfg))
            await self._r.create_if_not_exists(
                name=cfg["name"],
                provider_type="web-crawler",
                config_data=config_data,
            )
