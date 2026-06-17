from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from harmony.api.services.admin._data_sources import (  # noqa: PLC2701
    DataSourcesService,
)


@pytest.mark.asyncio
async def test_promote_creates_web_crawler_instances() -> None:
    service = DataSourcesService()
    service._repo = MagicMock()
    service._repo.create_if_not_exists = AsyncMock()

    crawl_config_service = MagicMock()
    crawl_config_service.list = AsyncMock(
        return_value=[
            {"name": "docs-site", "config_json": {"start_urls": ["https://x.test"]}},
        ]
    )

    await service.promote_crawler_configs(crawl_config_service)

    service._repo.create_if_not_exists.assert_awaited_once_with(
        name="docs-site",
        provider_type="web-crawler",
        config_data={"start_urls": ["https://x.test"]},
    )


@pytest.mark.asyncio
async def test_promote_is_idempotent() -> None:
    """Repeated promotion always delegates to create_if_not_exists, which is the
    ON CONFLICT (name) DO NOTHING upsert that makes promotion safe to re-run.
    """
    service = DataSourcesService()
    service._repo = MagicMock()
    service._repo.create_if_not_exists = AsyncMock()

    crawl_config_service = MagicMock()
    crawl_config_service.list = AsyncMock(
        return_value=[{"name": "docs-site", "config_json": {}}]
    )

    await service.promote_crawler_configs(crawl_config_service)
    await service.promote_crawler_configs(crawl_config_service)

    assert service._repo.create_if_not_exists.await_count == 2
    first_call, second_call = service._repo.create_if_not_exists.await_args_list
    assert first_call == second_call
